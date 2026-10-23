#!/usr/bin/env python3
"""Recompute traffic-sign categories and optional text similarity from sign-level pairs.

CSV columns: sample_token,sign_id,reference_category,predicted_category,origin.
origin must be detector_proposal or manually_added. For description scoring add
reference_description,predicted_description. Both descriptions must be present.

The fuzzy-Jaccard implementation is a *documented new reference option*, not
evidence that it matches the historical code behind the manuscript figure.
Confirm its exact preprocessing/threshold against original experiment logs.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from common import normalized, read_csv, write_csv, write_json

CATEGORIES = ("Regulatory", "Warning", "Information")
ORIGINS = ("detector_proposal", "manually_added")


def tokens(description: str) -> list[str]:
    text = unicodedata.normalize("NFKC", description).casefold()
    return sorted(set(re.findall(r"\w+", text)))


def text_jaccard(predicted: str, reference: str, metric: str, threshold: float) -> float:
    a, b = tokens(predicted), tokens(reference)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if metric == "token-jaccard":
        common = len(set(a) & set(b))
        return common / (len(a) + len(b) - common)

    # Weighted fuzzy intersection: greedy 1:1 token assignment, then
    # soft union = |A| + |B| - fuzzy_intersection. This is deterministic
    # but is not the only definition of fuzzy Jaccard in the literature.
    candidates = []
    for i, left in enumerate(a):
        for j, right in enumerate(b):
            sim = SequenceMatcher(None, left, right).ratio()
            if sim >= threshold:
                candidates.append((-sim, i, j))
    candidates.sort()
    used_a, used_b = set(), set()
    intersection = 0.0
    for negative_score, i, j in candidates:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            intersection -= negative_score
    return intersection / (len(a) + len(b) - intersection)


def evaluate(rows: list[dict], description_metric: str | None, threshold: float) -> tuple[dict, list[dict]]:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Similarity threshold must lie in [0, 1]")
    matrix = {label: {other: 0 for other in CATEGORIES} for label in CATEGORIES}
    origins = Counter()
    seen = set()
    per_item = []
    for item in rows:
        key = (normalized(item["sample_token"]), normalized(item["sign_id"]))
        if not all(key) or key in seen:
            raise ValueError(f"Empty or duplicate sample_token/sign_id: {key}")
        seen.add(key)
        reference = normalized(item["reference_category"])
        prediction = normalized(item["predicted_category"])
        origin = normalized(item["origin"])
        if reference not in CATEGORIES or prediction not in CATEGORIES:
            raise ValueError(f"Unknown category at {key}: {reference}, {prediction}")
        if origin not in ORIGINS:
            raise ValueError(f"Unknown detection origin at {key}: {origin}")
        matrix[reference][prediction] += 1
        origins[origin] += 1
        if description_metric:
            a = normalized(item.get("predicted_description"))
            b = normalized(item.get("reference_description"))
            if not a or not b:
                raise ValueError(f"Missing required description at {key}; do not treat missing text as a measured similarity")
            score = text_jaccard(a, b, description_metric, threshold)
            per_item.append({"sample_token": key[0], "sign_id": key[1], "reference_category": reference,
                             "similarity": round(score, 8)})
    size = len(rows)
    if not size:
        raise ValueError("No sign rows found")
    correct = sum(matrix[cat][cat] for cat in CATEGORIES)
    report = {
        "n_signs": size, "correct": correct, "classification_accuracy": correct / size,
        "labels": list(CATEGORIES), "confusion_matrix": [[matrix[r][p] for p in CATEGORIES] for r in CATEGORIES],
        "reference_counts": {r: sum(matrix[r].values()) for r in CATEGORIES},
        "prediction_counts": {p: sum(matrix[r][p] for r in CATEGORIES) for p in CATEGORIES},
        "per_category_recall": {r: matrix[r][r] / sum(matrix[r].values()) if sum(matrix[r].values()) else None for r in CATEGORIES},
        "detection_origin_counts": dict(origins),
    }
    if description_metric:
        counts = {r: [0] * 5 for r in CATEGORIES}
        for row in per_item:
            bucket = min(4, int(row["similarity"] * 5))  # 1.0 -> last bin
            counts[row["reference_category"]][bucket] += 1
        report["description_metric"] = {"method": description_metric, "threshold": threshold,
            "bin_intervals": ["[0.0,0.2)", "[0.2,0.4)", "[0.4,0.6)", "[0.6,0.8)", "[0.8,1.0]"],
            "histogram_counts": counts,
            "histogram_percent": {cat: [100 * n / report["reference_counts"][cat] if report["reference_counts"][cat] else None
                                         for n in counts[cat]] for cat in CATEGORIES},
            "historical_metric_confirmed": False}
    return report, per_item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--description-metric", choices=("token-jaccard", "fuzzy-jaccard"))
    parser.add_argument("--fuzzy-threshold", type=float, default=0.8)
    args = parser.parse_args()
    required = ("sample_token", "sign_id", "reference_category", "predicted_category", "origin")
    if args.description_metric:
        required += ("reference_description", "predicted_description")
    result, text_scores = evaluate(read_csv(args.input, required), args.description_metric, args.fuzzy_threshold)
    folder = Path(args.output_dir)
    write_json(folder / "sign_category_metrics.json", result)
    write_csv(folder / "confusion_matrix.csv", ["reference_category", *CATEGORIES, "total"],
              [{"reference_category": c, **{pred: result["confusion_matrix"][i][j] for j, pred in enumerate(CATEGORIES)},
                "total": result["reference_counts"][c]} for i, c in enumerate(CATEGORIES)])
    if args.description_metric:
        write_csv(folder / "semantic_similarity_by_sign.csv",
                  ["sample_token", "sign_id", "reference_category", "similarity"], text_scores)
    print(json.dumps({"n_signs": result["n_signs"], "classification_accuracy": result["classification_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
