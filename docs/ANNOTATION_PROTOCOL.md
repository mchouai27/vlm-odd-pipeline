# Annotation protocol

Four annotators developed a common annotation guide and reviewed pilot scenes together to align their interpretation of the ODD fields. The 850 scenes were subsequently distributed for scene-level verification. The review process focused on representative scene anchors and frames flagged by automatic consistency checks.

The [annotation guide](annotation_guidelines.pdf) describes the labeling conventions. The two review interfaces are provided in [`ui/review_raw/`](../ui/review_raw/) and [`ui/review_flags/`](../ui/review_flags/).

## Label provenance

For reproducible evaluation, label exports distinguish inspected samples from automatically propagated values and maintain the original `scene_token` and `sample_token`. Annotation-stage agreement is measured against the explicitly selected manual-reference population.
