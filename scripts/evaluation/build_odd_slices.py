#!/usr/bin/env python3
"""Build disjoint ODD evaluation pairs from actual V3 rows and official val tokens.

The six binary decisions reflect the reported *slice descriptions*; their exact
historical input conventions must be confirmed before manuscript reproduction.
Missing or ambiguous values stop the command; there is no silent assignment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from common import load_tokens, normalized, read_csv, write_json

PAIRS = (
    ("day_good_illumination", "night_low_illumination"),
    ("low_medium_traffic", "high_traffic"),
    ("non_crossroad", "crossroad"),
    ("lanes_le_2", "lanes_ge_3"),
    ("no_pedestrian_crossing", "pedestrian_crossing"),
    ("no_water_droplets", "water_droplets"),
)


def yes_no(value: str, field: str, token: str) -> bool:
    clean = normalized(value).casefold()
    if clean not in ("yes", "no"):
        raise ValueError(f"{token} {field}: expected Yes/No; received {value!r}")
    return clean == "yes"


def classify(row: dict[str, str], config: dict[str, str]) -> list[str]:
    token = row["sample_token"]
    day = yes_no(row[config["day"]], "day", token)
    night = yes_no(row[config["night"]], "night", token)
    if day == night:
        raise ValueError(f"{token}: Day/Night flags not exclusive and exhaustive")
    traffic = normalized(row[config["volume"]]).casefold()
    if traffic not in ("high", "medium", "low"):
        raise ValueError(f"{token}: unknown VolumeOfTraffic {traffic!r}")
    crossing = yes_no(row[config["crossroad"]], "crossroad", token)
    pedestrian = yes_no(row[config["pedestrian_crossing"]], "pedestrian_crossing", token)
    water = yes_no(row[config["standing_water"]], "standing_water", token)
    droplets = yes_no(row[config["droplet_cues"]], "droplet_cues", token)
    try:
        lanes = float(normalized(row[config["lanes"]]))
    except ValueError as exc:
        raise ValueError(f"{token}: invalid lane count {row[config['lanes']]!r}") from exc
    if not lanes.is_integer() or lanes < 1:
        raise ValueError(f"{token}: lane count must be positive integer")
    binary = (night, traffic == "high", crossing, lanes >= 3, pedestrian, water or droplets)
    return [pair[int(positive)] for pair, positive in zip(PAIRS, binary)]


def build(rows: list[dict[str, str]], val_tokens: list[str], config: dict[str, str]) -> dict[str, list[str]]:
    if len(val_tokens) != len(set(val_tokens)):
        raise ValueError("Duplicate validation tokens")
    selected = set(val_tokens)
    by_token = {}
    for row in rows:
        token = normalized(row["sample_token"])
        if token in selected:
            if token in by_token:
                raise ValueError(f"Duplicate V3 sample_token: {token}")
            by_token[token] = row
    missing = selected - set(by_token)
    if missing:
        raise ValueError(f"Missing {len(missing)} official validation tokens in V3, e.g. {sorted(missing)[0]}")
    slices = {key: [] for pair in PAIRS for key in pair}
    slices["overall"] = list(val_tokens)
    for token in val_tokens:
        for key in classify(by_token[token], config):
            slices[key].append(token)
    for left, right in PAIRS:
        if set(slices[left]) & set(slices[right]) or len(slices[left]) + len(slices[right]) != len(val_tokens):
            raise AssertionError(f"Invalid partition: {left}/{right}")
    return slices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, help="Wide, final V3 CSV keyed by sample_token")
    parser.add_argument("--val-tokens", required=True, help="Official nuScenes val tokens from export_val_tokens.py")
    parser.add_argument("--columns", required=True, help="Reviewed copy of configs/slice_columns.example.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-counts", help="Optional real or paper-reported condition counts JSON for strict comparison")
    args = parser.parse_args()
    columns = json.loads(Path(args.columns).read_text(encoding="utf-8"))
    required = ("sample_token", *[value for key, value in columns.items() if not key.startswith("_")])
    annotations = read_csv(args.annotations, required)
    tokens = load_tokens(args.val_tokens)
    slices = build(annotations, tokens, columns)
    if args.expected_counts:
        expected = json.loads(Path(args.expected_counts).read_text(encoding="utf-8"))
        if "expected_slice_counts" in expected:
            expected = expected["expected_slice_counts"]
        if not isinstance(expected, dict) or set(expected) != set(slices):
            raise ValueError("Expected-counts file must list exactly the thirteen named ODD conditions")
        discrepancies = {name: (expected[name], len(slices[name])) for name in expected if name in slices and expected[name] != len(slices[name])}
        if discrepancies:
            raise ValueError(f"ODD condition counts disagree with expected counts: {discrepancies}")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for key, sample_tokens in slices.items():
        (output / f"{key}.txt").write_text("\n".join(sample_tokens) + "\n", encoding="utf-8")
    write_json(output / "manifest.json", {
        "source": "V3 ODD annotation CSV intersected with the supplied official nuScenes validation tokens",
        "counts": {name: len(tokens) for name, tokens in slices.items()},
        "columns": columns, "pairs": PAIRS,
        "input_sha256": {"annotations": hashlib.sha256(Path(args.annotations).read_bytes()).hexdigest(),
                         "val_tokens": hashlib.sha256(Path(args.val_tokens).read_bytes()).hexdigest()},
    })
    print(json.dumps({name: len(tokens) for name, tokens in slices.items()}, indent=2))


if __name__ == "__main__":
    main()
