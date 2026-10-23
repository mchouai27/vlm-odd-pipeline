#!/usr/bin/env python3
"""Compare re-evaluated results against the supplied manuscript's target values.

This script never treats manuscript values as evidence of experiment outputs.
Missing input files remain explicit NOT VERIFIED findings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import read_csv, write_json


def compare(expected: dict, *, annotation: dict | None = None,
            signs: dict | None = None, detection: list[dict] | None = None,
            slices: dict | None = None) -> list[dict]:
    checks: list[dict] = []

    def add(name: str, target, observed, tolerance: float) -> None:
        if observed is None:
            checks.append({"claim": name, "expected": target, "observed": None, "status": "NOT VERIFIED"})
        else:
            valid = abs(observed - target) <= tolerance if isinstance(target, (int, float)) else observed == target
            checks.append({"claim": name, "expected": target, "observed": observed,
                           "status": "PASS" if valid else "MISMATCH"})

    for stage, target in expected["annotation_macro_f1"].items():
        actual = annotation.get("macro_f1", {}).get(stage) if annotation else None
        add(f"RQ1 macro-F1 {stage}", target, actual, 0.0005)
    details = {item["attribute"]: item for item in annotation.get("attributes", [])} if annotation else {}
    for attribute, values in expected.get("annotation_per_attribute_f1", {}).items():
        for stage, target in zip(("V0", "V1", "V2", "V3"), values):
            entry = details.get(attribute)
            add(f"RQ1 {attribute} {stage}", target, float(entry[stage]) if entry else None, 0.0051)
    add("Number of validated traffic signs", expected["dataset"]["traffic_signs"],
        signs.get("n_signs") if signs else None, 0)
    for i, row in enumerate(expected["traffic_sign_confusion"]):
        for j, target in enumerate(row):
            actual = signs["confusion_matrix"][i][j] if signs else None
            add(f"Traffic sign confusion cell [{i},{j}]", target, actual, 0)
    for name, target in expected["expected_slice_counts"].items():
        add(f"ODD slice count {name}", target, slices.get("counts", {}).get(name) if slices else None, 0)
    if detection is not None:
        lookup = {(record["model"], record["condition"]): record for record in detection}
        if len(lookup) != len(detection):
            raise ValueError("Duplicate model/ODD-condition rows")
    else:
        lookup = {}
    for model, conditions in expected["detection_metrics_percent"].items():
        for condition, (m_ap, nds) in conditions.items():
            result = lookup.get((model, condition))
            add(f"{model} {condition} mAP", m_ap,
                float(result["mAP_percent"]) if result else None, 0.055 if round(m_ap, 1) == m_ap else 0.0055)
            add(f"{model} {condition} NDS", nds,
                float(result["NDS_percent"]) if result else None, 0.055 if round(nds, 1) == nds else 0.0055)
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, help="configs/manuscript_targets.json")
    parser.add_argument("--annotation", help="Generated annotation_stage_metrics.json")
    parser.add_argument("--signs", help="Generated sign_category_metrics.json")
    parser.add_argument("--detection", help="Generated odd_detection_metrics.csv")
    parser.add_argument("--slices", help="Generated ODD slice manifest.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8")) if path else None
    detection = read_csv(args.detection, ("model", "condition", "mAP_percent", "NDS_percent")) if args.detection else None
    comparison = compare(load(args.targets), annotation=load(args.annotation), signs=load(args.signs),
                         detection=detection, slices=load(args.slices))
    summary = {status: sum(check["status"] == status for check in comparison)
               for status in ("PASS", "MISMATCH", "NOT VERIFIED")}
    write_json(args.output, {"summary": summary, "checks": comparison})
    print(json.dumps(summary, indent=2))
    if summary["MISMATCH"]:
        raise SystemExit(1)
    if summary["NOT VERIFIED"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
