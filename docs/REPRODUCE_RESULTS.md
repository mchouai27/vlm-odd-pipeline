# Reproduce the experiments

This guide covers the annotation-stage, traffic-sign, and ODD-sliced 3D detection evaluations used in the IV 2027 study. The scripts operate on token-linked annotation exports, corresponding model predictions, and nuScenes data. [`configs/manuscript_targets.json`](../configs/manuscript_targets.json) provides the values reported in the manuscript for comparison with computed results.

## 0. Set up the environment

From the repository root, run:

```bash
python -m pip install -r requirements.txt
mkdir -p run_outputs
python -m pip freeze > run_outputs/environment_frozen.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Download nuScenes `v1.0-trainval` separately. Keep camera images, credentials, and third-party model weights outside version control.

## 1. Stage agreement, RQ1

Export the stage labels for evaluated examples into
`annotations/annotation_stages_long.csv`. One row per `(sample_token,attribute)`:

| sample_token | attribute | reference | V0 | V1 | V2 | V3 | reference_origin (optional) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nuScenes token | evaluated attribute | manual reference | raw proposal | canonicalised | automatic QC | post-review | inspected / propagated |

The CSV covers all 21 attributes with a common reference population. Export the valid class lists to
`configs/evaluated_categories.json`:

```json
{"StandingWater": ["Yes", "No"], "Illumination": ["Day", "Night"]}
```

The JSON illustrates the expected structure. Define the valid categories for all evaluated attributes. These metrics measure agreement with the manual reference.

```bash
python scripts/evaluation/evaluate_annotation_stages.py \
  --input annotations/annotation_stages_long.csv \
  --categories configs/evaluated_categories.json \
  --output-dir results/annotation_stages
```

The output contains `annotation_stage_metrics.json` and
`per_attribute_f1.csv`; both are computed from the input labels, not loaded
from the paper table.

## 2. Traffic signs

Export one paired record for each validated traffic sign to
`annotations/signs_verified.csv`:

`sample_token,sign_id,reference_category,predicted_category,origin,reference_description,predicted_description`

Use `Regulatory`, `Warning`, and `Information` for the categories and `detector_proposal` or `manually_added` for the origin. Preserve prediction-to-reference associations. Annotator-added signs remain part of the verified set. The classification tool expects a predicted category on each evaluated row.

```bash
python scripts/evaluation/evaluate_traffic_signs.py \
  --input annotations/signs_verified.csv \
  --output-dir results/traffic_signs
```

Optionally compute description similarity:

```bash
python scripts/evaluation/evaluate_traffic_signs.py \
  --input annotations/signs_verified.csv \
  --description-metric fuzzy-jaccard \
  --fuzzy-threshold 0.8 \
  --output-dir results/traffic_signs
```

The optional fuzzy-Jaccard implementation uses NFKC case-folded token sets, SequenceMatcher similarity, greedy one-to-one matching, and a weighted Jaccard union. Use the original experiment settings when reproducing the paper's semantic-similarity figure.

## 3. Construct official ODD validation subsets

Export final annotation rows to `annotations/final_odd_v3.csv` with one row
per sample_token (and `scene_token`) and the full ODD field columns. Check
`configs/slice_columns.example.json` against your actual V3 output and copy it
as `configs/slice_columns.json`. This script requires an exclusive Day/Night
assignment, an integer lane count, a low/medium/high traffic class and
Yes/No fields for the other conditions. Verify these are the **same rules**
and field aggregation used in your original experiment.

```bash
python scripts/evaluation/export_val_tokens.py \
  --dataroot /data/nuscenes \
  --output run_outputs/official_val_tokens.txt

python scripts/evaluation/build_odd_slices.py \
  --annotations annotations/final_odd_v3.csv \
  --val-tokens run_outputs/official_val_tokens.txt \
  --columns configs/slice_columns.json \
  --output-dir results/detection/slices
```

All six pairs must partition the *same* 6,019 keyframes. Inspect the
resulting `manifest.json`, and use the manuscript's counts as an audit:

```bash
python scripts/evaluation/build_odd_slices.py \
  --annotations annotations/final_odd_v3.csv \
  --val-tokens run_outputs/official_val_tokens.txt \
  --columns configs/slice_columns.json \
  --expected-counts configs/manuscript_targets.json \
  --output-dir results/detection/slices
```

The script reads `expected_slice_counts` from the supplied target file.
If counts disagree, **investigate the ODD definitions**, do not tune labels
just to match table counts.

## 4. Rerun official mAP/NDS evaluation

Store the two **unchanged, full-validation** official nuScenes detection
JSON files as `results/detection/bevfusion_val.json` and
`results/detection/bevformer_tiny_val.json`. Confirm their `meta` fields
specify `use_camera=true` and no LiDAR or radar. Store corresponding run
configs and real checkpoint SHA-256 values in
`configs/model_provenance.json` (using the `.example.json` as a template).

```bash
python scripts/evaluation/evaluate_detection_slices.py \
  --dataroot /data/nuscenes \
  --slices results/detection/slices \
  --model BEVFusion=results/detection/bevfusion_val.json \
  --model BEVFormer-Tiny=results/detection/bevformer_tiny_val.json \
  --output-dir results/detection
```

The script instantiates nuScenes' official detection evaluator with its
token-level ground-truth/prediction loading path, uses configuration
`detection_cvpr_2019`, writes each official `metrics_summary.json`, and
exports a combined `odd_detection_metrics.csv` plus hashes and devkit version.
This integration follows the official devkit's [detection evaluator](https://github.com/nutonomy/nuscenes-devkit/blob/master/python-sdk/nuscenes/eval/detection/evaluate.py)
and [sample-token loaders](https://github.com/nutonomy/nuscenes-devkit/blob/master/python-sdk/nuscenes/eval/common/loaders.py).

## 5. Compare results with the manuscript

```bash
python scripts/evaluation/compare_to_manuscript.py \
  --targets configs/manuscript_targets.json \
  --annotation results/annotation_stages/annotation_stage_metrics.json \
  --signs results/traffic_signs/sign_category_metrics.json \
  --slices results/detection/slices/manifest.json \
  --detection results/detection/odd_detection_metrics.csv \
  --output results/manuscript_comparison.json

```

The comparison script checks calculated metrics against the manuscript reference values. This requires the original stage-level annotations, traffic-sign records, and detector predictions; the reference file alone cannot recreate those measurements.
