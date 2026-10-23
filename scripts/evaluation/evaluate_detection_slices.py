#!/usr/bin/env python3
"""Run the *official* nuScenes detection metric logic over keyframe ODD subsets.

Input detections are the original fixed full-val nuScenes results JSON for each
model; this code NEVER changes detections or trains anything. It uses the
devkit's supported token-specific prediction/GT loaders for each subset.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch

from common import load_tokens, write_csv, write_json


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def run(args: argparse.Namespace) -> list[dict]:
    # Import here to keep --help, smoke tests and other scripts usable offline.
    from nuscenes import NuScenes
    from nuscenes.eval.common.config import config_factory
    from nuscenes.eval.detection import evaluate as devkit_eval
    from nuscenes.utils.splits import create_splits_scenes

    nusc = NuScenes(version=args.version, dataroot=args.dataroot, verbose=False)
    valid_scenes = set(create_splits_scenes()["val"])
    official = {sample["token"] for sample in nusc.sample
                if nusc.get("scene", sample["scene_token"])["name"] in valid_scenes}
    if args.version == "v1.0-trainval" and len(official) != 6019:
        raise ValueError(f"Unexpected official validation split size: {len(official)}")
    subset_files = sorted(Path(args.slices).glob("*.txt"))
    if not subset_files:
        raise ValueError("No .txt subset files found: generate them from V3 first")
    subsets = {path.stem: load_tokens(path) for path in subset_files}
    if "overall" not in subsets or set(subsets["overall"]) != official:
        raise ValueError("overall.txt must contain the exact official validation sample tokens")
    for name, tokens in subsets.items():
        if not set(tokens).issubset(official):
            raise ValueError(f"{name}: contains a token outside the official validation split")

    models = {}
    for item in args.model:
        if "=" not in item:
            raise ValueError("--model must be NAME=/path/to/full_validation_results.json")
        name, path = item.split("=", 1)
        if not name or not path or name in models or not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid or duplicate model specification: {item}")
        models[name] = Path(path)

    scores: list[dict] = []
    cfg = config_factory("detection_cvpr_2019")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model_hashes = {}
    for model_name, filepath in models.items():
        submission = json.loads(filepath.read_text(encoding="utf-8"))
        predictions = submission.get("results")
        if not isinstance(predictions, dict) or not isinstance(submission.get("meta"), dict):
            raise ValueError(f"Invalid official nuScenes result format: {filepath}")
        if set(predictions) != official:
            missing, extra = official - set(predictions), set(predictions) - official
            raise ValueError(f"{model_name}: predictions must cover all val keyframes; missing {len(missing)}, extra {len(extra)}")
        if submission["meta"].get("use_camera") is not True or any(submission["meta"].get(key)
           for key in ("use_lidar", "use_radar")):
            raise ValueError(f"{model_name}: metadata does not specify a camera-only detector")
        model_hashes[model_name] = sha256(filepath)
        for subset_name, sample_tokens in subsets.items():
            eval_dir = out / model_name / subset_name
            # A custom sample-token split, rather than the devkit's built-in
            # scene-level split. This patch is local to evaluator creation.
            with patch.object(devkit_eval, "get_samples_of_custom_split", return_value=sample_tokens):
                evaluator = devkit_eval.DetectionEval(
                    nusc=nusc, config=cfg, result_path=str(filepath),
                    eval_set="odd_keyframe_subset", output_dir=str(eval_dir), verbose=False)
            result = evaluator.main(plot_examples=0, render_curves=False)
            scores.append({"model": model_name, "condition": subset_name,
                           "n_keyframes": len(sample_tokens),
                           "mAP_percent": 100.0 * result["mean_ap"],
                           "NDS_percent": 100.0 * result["nd_score"]})
            print(f"{model_name:20s} {subset_name:30s}: {len(sample_tokens):5d} frames | "
                  f"mAP {scores[-1]['mAP_percent']:.2f} | NDS {scores[-1]['NDS_percent']:.2f}")
    overall = {row["model"]: row["mAP_percent"] for row in scores if row["condition"] == "overall"}
    for row in scores:
        row["delta_mAP_percent"] = row["mAP_percent"] - overall[row["model"]]
    write_csv(out / "odd_detection_metrics.csv",
              ["model", "condition", "n_keyframes", "mAP_percent", "NDS_percent", "delta_mAP_percent"], scores)
    write_json(out / "provenance.json", {
        "source": "nuScenes official detection evaluation, token-specific GT and prediction loaders",
        "config": "detection_cvpr_2019", "version": args.version,
        "devkit_package_version": importlib.metadata.version("nuscenes-devkit"),
        "prediction_sha256": model_hashes,
        "count_by_condition": {name: len(tokens) for name, tokens in subsets.items()},
    })
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataroot", required=True, help="Local nuScenes trainval root")
    parser.add_argument("--version", default="v1.0-trainval")
    parser.add_argument("--slices", required=True, help="Folder of sample token .txt subsets")
    parser.add_argument("--model", action="append", required=True,
                        help="Repeat: BEVFusion=/path/to/results.json --model BEVFormer-Tiny=/path/to/results.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
