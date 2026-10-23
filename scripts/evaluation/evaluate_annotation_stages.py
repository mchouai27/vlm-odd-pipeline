#!/usr/bin/env python3
"""Evaluate actual V0-V3 outputs against a supplied manual-reference CSV.

Input is *long form*: one unique (sample_token, attribute) row, with columns
sample_token,attribute,reference,V0,V1,V2,V3. Optionally add reference_origin.
The valid categories for each attribute MUST be provided explicitly in JSON:
{"Illumination": ["Day", "Night"], "StandingWater": ["Yes", "No"]}.
No synthetic labels, missing-label imputation, or silent category inference.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from common import normalized, read_csv, write_csv, write_json

STAGES = ("V0", "V1", "V2", "V3")


def per_class_f1(reference: list[str], predicted: list[str], categories: list[str]) -> float:
    if len(reference) != len(predicted):
        raise ValueError("Prediction/reference length mismatch")
    if not reference:
        raise ValueError("Cannot score an empty attribute")
    scores = []
    for label in categories:
        tp = sum(truth == label and guess == label for truth, guess in zip(reference, predicted))
        fp = sum(truth != label and guess == label for truth, guess in zip(reference, predicted))
        fn = sum(truth == label and guess != label for truth, guess in zip(reference, predicted))
        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def evaluate(rows: list[dict], categories_by_attribute: dict[str, list[str]]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        token = normalized(row["sample_token"])
        attr = normalized(row["attribute"])
        if not token or not attr:
            raise ValueError("Empty sample_token or attribute")
        key = (token, attr)
        if key in seen:
            raise ValueError(f"Duplicate evaluation item: {key}")
        seen.add(key)
        if attr not in categories_by_attribute:
            raise ValueError(f"Missing explicit valid categories for attribute {attr}")
        labels = categories_by_attribute[attr]
        if not isinstance(labels, list) or len(labels) != len(set(labels)) or not labels or not all(normalized(x) for x in labels):
            raise ValueError(f"Invalid category list for {attr}")
        for field in ("reference", *STAGES):
            if normalized(row[field]) not in labels:
                raise ValueError(f"Unrecognized {field}={row[field]!r} for {attr} at {token}; clean upstream")
        grouped[attr].append(row)
    if set(grouped) != set(categories_by_attribute):
        raise ValueError("Category specification and input attributes differ; do not silently omit attributes")

    details = []
    for attribute in sorted(grouped):
        examples = grouped[attribute]
        truth = [normalized(row["reference"]) for row in examples]
        detail = {"attribute": attribute, "n": len(examples)}
        for stage in STAGES:
            predicted = [normalized(row[stage]) for row in examples]
            detail[stage] = per_class_f1(truth, predicted, categories_by_attribute[attribute])
        details.append(detail)

    return {
        "description": "Agreement with the supplied manual reference, not independent final-label accuracy",
        "attributes": details,
        "macro_f1": {stage: sum(row[stage] for row in details) / len(details) for stage in STAGES},
        "n_unique_samples": len({row["sample_token"] for row in rows}),
        "n_reference_pairs": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Long-form V0-V3/reference CSV")
    parser.add_argument("--categories", required=True, help="JSON mapping evaluated attribute to valid classes")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    rows = read_csv(args.input, ("sample_token", "attribute", "reference", *STAGES))
    categories = json.loads(Path(args.categories).read_text(encoding="utf-8"))
    if not isinstance(categories, dict):
        raise ValueError("Categories JSON must be a mapping of attribute to nonempty category list")
    result = evaluate(rows, categories)
    folder = Path(args.output_dir)
    write_csv(folder / "per_attribute_f1.csv", ["attribute", "n", *STAGES], result["attributes"])
    write_json(folder / "annotation_stage_metrics.json", result)
    print(json.dumps(result["macro_f1"], indent=2))


if __name__ == "__main__":
    main()
