# Processing

Utilities to turn raw VLM outputs into a **clean, normalized, and semantically consistent** dataset.
No hardcoded paths — everything is CLI-driven.

Contents:
- `preprocess_normalize.py` — categorical cleanup, lane normalization, rainfall/density mapping, optional consistency flags.
- `semantic_scene_consistency.py` — scene-level semantic checks (toggle spikes, lane jumps, cloudiness transitions, construction logic, illumination).

---

## Quick start

```bash
# 1) Clean & normalize (CSV in → cleaned CSV out)
python processing/preprocess_normalize.py   --input path/to/annotations.csv   --output cleaned_annotations.csv   --report checks_report.json

# 2) Run semantic checks (adds *_check columns)
python processing/semantic_scene_consistency.py   --input cleaned_annotations.csv   --output merged_with_semantic_flags.csv   --report semantic_flags_report.json   --scene-col Scene
```

---

## `preprocess_normalize.py`

**What it does**
- Fix noisy categorical values (e.g., `'Yes, No' → 'No'`, `'Yes (partial)' → 'Yes'`, `'Possible'/'Maybe' → 'No'`).
- Normalize lane counts from messy strings to integers.
- Map rainfall visibility to a canonical set; force known columns to `'No'` when appropriate.
- Normalize traffic density (`'Moderate' → 'Medium'`).
- (Optional) Add basic consistency flags and emit a JSON report.

**Usage**
```bash
python processing/preprocess_normalize.py   --input annotations.csv   --output cleaned_annotations.csv   --report checks_report.json
```

**Key arguments**
- `--input` (required): input CSV.
- `--output` (required): cleaned CSV path.
- `--report` (optional): JSON summary (counts of flagged issues, rows, etc.).

**Notes**
- Requires a `Scene` column for sequence-aware checks; if absent, those checks are skipped.
- Lane normalization falls back sensibly when values are already numeric.

---

## `semantic_scene_consistency.py`

**Checks performed (per scene)**
- **Immediate Yes/No toggles** in `*_Auto_Check` sequences (e.g., `Yes, No, Yes`).
- **Divided vs Undivided** contradictions (both equal).
- **Lane jumps**: sudden ±2 or more lanes frame-to-frame.
- **Signs vs TimeOfOperation**: list-length mismatches for regulatory/warning/information signs.
- **Construction logic**:
  - `RoadWorks = Yes` ⇒ `TemporaryRoadSignage` should be `Yes`.
  - `TemporaryLineMarkers = Yes` while both RoadWorks & Signage are `No` ⇒ suspicious.
- **Illumination**: Day and Night cannot be equal (both Yes/No).
- **Cloudiness transitions**: Clear ↔ Overcast must pass through PartlyCloudy (unless a one-sample detour); also applies zig-zag smoothing and exclusivity.

**Usage**
```bash
python processing/semantic_scene_consistency.py   --input merged_flat_data_corrected_auto_check.csv   --output merged_with_semantic_flags.csv   --report semantic_flags_report.json   --scene-col Scene
```

**Common overrides (schema differences)**
```bash
python processing/semantic_scene_consistency.py   --input cleaned_annotations.csv   --output with_flags.csv   --scene-col Scene   --lanes-col "Scenery.DrivableArea.LaneSpecification.NumberOfLanes_Auto_Check"   --divided-col "Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Divided_Auto_Check"   --undivided-col "Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Undivided_Auto_Check"   --cloud-clear-col  "EnvironmentalConditions.Weather.Cloudiness.Clear_Auto_Check"   --cloud-partly-col "EnvironmentalConditions.Weather.Cloudiness.PartlyCloudy_Auto_Check"   --cloud-overcast-col "EnvironmentalConditions.Weather.Cloudiness.Overcast_Auto_Check"
```

**Outputs**
- CSV identical to input **plus** `_check` columns (`'OK'` or reason strings).
- Optional JSON report with per-column issue counts.

---

## Typical processing stage

1. **Normalize**: `preprocess_normalize.py` → `cleaned_annotations.csv` (+ `checks_report.json`).
2. **Validate semantics**: `semantic_scene_consistency.py` → `merged_with_semantic_flags.csv` (+ `semantic_flags_report.json`).

---

## Tips

- Columns ending with `_Auto_Check` are treated as smoothed/derived signals for temporal logic.
- Missing columns are **skipped with warnings** — scripts won’t crash if a field is absent.
