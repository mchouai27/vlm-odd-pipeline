#!/usr/bin/env python3
"""
Semantic Consistency Checks Across Scene Coherence

Applies a suite of temporal/structural validations over per-sample annotations,
grouped by Scene. Flags unlikely toggles, contradictory states, and incoherent
transitions. Produces an augmented CSV with *_check columns and an optional JSON
summary of issue counts.

All paths and column names are user-provided via CLI arguments.

Usage:
  python vlm_integration/semantic_scene_consistency.py \
    --input merged_flat_data_corrected_auto_check.csv \
    --output merged_with_semantic_flags.csv \
    --report semantic_flags_report.json \
    --scene-col Scene

Notes:
  - By default, the script runs a curated set of checks. You can override
    column names via flags. Missing columns are skipped with warnings.
"""

import os
import json
import argparse
from typing import Dict, Any, List, Tuple

import pandas as pd
import ast


# ----------------------------- Helpers ------------------------------------ #

def warn_missing(df: pd.DataFrame, cols: List[str]) -> List[str]:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"[warn] Missing columns (skipped): {missing}")
    return missing


def safe_list_len(x) -> int:
    """Try to parse stringified list and return its length; return -1 on failure."""
    if isinstance(x, list):
        return len(x)
    if isinstance(x, (tuple, set)):
        return len(list(x))
    if pd.isna(x):
        return -1
    s = str(x).strip()
    # Try JSON first
    try:
        obj = json.loads(s)
        return len(obj) if isinstance(obj, list) else -1
    except Exception:
        pass
    # Fallback to Python literal
    try:
        obj = ast.literal_eval(s)
        return len(obj) if isinstance(obj, list) else -1
    except Exception:
        return -1


# ----------------------------- Check 0: Local toggles --------------------- #

def get_issue_labels(sequence: List[Any]) -> List[str]:
    """
    Label 'immediate entry/exit' anomalies in Yes/No sequences:
    - ... Yes, No, Yes ...  -> "Immediate exit/re-entry" at the middle index
    - ... No, Yes, No ...   -> "Immediate entry/exit"   at the middle index
    """
    labels = ["OK"] * len(sequence)
    i = 1
    while i < len(sequence) - 1:
        prev_v, v, next_v = sequence[i - 1], sequence[i], sequence[i + 1]
        if v == "No" and prev_v == "Yes" and next_v == "Yes":
            labels[i] = "Immediate exit/re-entry"
            i += 2
            continue
        if v == "Yes" and prev_v == "No" and next_v == "No":
            labels[i] = "Immediate entry/exit"
            i += 2
            continue
        i += 1
    return labels


def add_problem_flags(df: pd.DataFrame, scene_col: str, base_cols: List[str]) -> pd.DataFrame:
    """
    For each base column, read its *_Auto_Check sequence per scene, and emit a
    new column named *_Auto_Check_check with row-wise labels ("OK" or issue text).
    """
    missing = [c for c in base_cols if f"{c}_Auto_Check" not in df.columns]
    if missing:
        print(f"[warn] add_problem_flags: missing *_Auto_Check columns for {missing}")

    out = df.copy()
    for scene_token, scene_df in df.groupby(scene_col):
        mask = df[scene_col] == scene_token
        for base_col in base_cols:
            auto_col = f"{base_col}_Auto_Check"
            if auto_col not in df.columns:
                continue
            seq = scene_df[auto_col].tolist()
            out.loc[mask, f"{auto_col}_check"] = get_issue_labels(seq)
    return out


# ----------------------------- Check 1: Divided/Undivided ----------------- #

def check_divided_undivided_consistency(
    df: pd.DataFrame, divided_col: str, undivided_col: str
) -> pd.DataFrame:
    """
    Flags if Divided and Undivided are equal ('Yes'/'Yes' or 'No'/'No').
    """
    if divided_col not in df.columns or undivided_col not in df.columns:
        print(f"[warn] check_divided_undivided_consistency: columns not found: {divided_col}, {undivided_col}")
        return df

    out = df.copy()
    colname = "Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Divided_Undivided_check"
    out[colname] = "OK"

    valid = out[divided_col].notna() & out[undivided_col].notna()
    bad = valid & ((out[divided_col] == out[undivided_col]))
    out.loc[bad, colname] = "Divided/Undivided inconsistency (both equal)"
    return out


# ----------------------------- Check 2: Lanes jumps ----------------------- #

def flag_number_of_lanes(df: pd.DataFrame, scene_col: str, lanes_col: str) -> pd.DataFrame:
    """
    For each scene, flag sudden changes of 2+ lanes between adjacent samples.
    Emits <lanes_col>_check column with 'OK' or 'Sudden addition/reduction of N lanes'.
    """
    if lanes_col not in df.columns:
        print(f"[warn] flag_number_of_lanes: column not found: {lanes_col}")
        return df

    out = df.copy()
    check_col = f"{lanes_col}_check"
    out[check_col] = "OK"

    for scene_token, scene_df in df.groupby(scene_col):
        scene_df = scene_df.reset_index()
        vals = scene_df[lanes_col].tolist()
        for i in range(1, len(vals)):
            try:
                diff = float(vals[i]) - float(vals[i - 1])
            except Exception:
                continue
            if abs(diff) >= 2:
                transition = "addition" if diff > 0 else "reduction"
                idx = scene_df.loc[i, "index"]
                out.loc[idx, f"{lanes_col}_check"] = f"Sudden {transition} of {int(abs(diff))} lanes"
    return out


# ----------------------------- Check 3: Signs vs Times -------------------- #

def check_signs_time_pairs(
    df: pd.DataFrame,
    pairs: List[Tuple[str, str]],
) -> pd.DataFrame:
    """
    For each (signs_col, times_col), compare list lengths; emit *_pair_check columns.
    If parsing fails or lengths differ, flag mismatch.
    """
    out = df.copy()
    for signs_col, times_col in pairs:
        if signs_col not in df.columns or times_col not in df.columns:
            print(f"[warn] check_signs_time_pairs: missing {signs_col} or {times_col}")
            continue
        check_col = f"{signs_col}_pair_check"
        out[check_col] = "OK"
        for i in range(len(out)):
            l_signs = safe_list_len(out.at[i, signs_col])
            l_times = safe_list_len(out.at[i, times_col])
            if l_signs == -1 or l_times == -1:
                out.at[i, check_col] = "Parse error (non-list)"
            elif l_signs != l_times:
                out.at[i, check_col] = f"Length mismatch (signs={l_signs}, times={l_times})"
    return out


# ----------------------------- Check 4: Construction zone ----------------- #

def check_construction_zone(
    df: pd.DataFrame,
    roadworks_col: str,
    signage_col: str,
    linemarkers_col: str,
) -> pd.DataFrame:
    """
    Combined logic:
      - If RoadWorks == 'Yes' then TemporaryRoadSignage should be 'Yes'
      - If TemporaryLineMarkers == 'Yes' while both RoadWorks and Signage == 'No' → suspicious
    Emits <roadworks_col>_check with 'OK' or issue text.
    """
    for c in (roadworks_col, signage_col, linemarkers_col):
        if c not in df.columns:
            print(f"[warn] check_construction_zone: missing column {c}")
            return df

    out = df.copy()
    check_col = f"{roadworks_col}_check"
    out[check_col] = "OK"

    for i in range(len(out)):
        rw = out.at[i, roadworks_col]
        sign = out.at[i, signage_col]
        lines = out.at[i, linemarkers_col]

        # Rule 1
        if rw == "Yes" and sign == "No":
            out.at[i, check_col] = "RoadWorks present but missing TemporaryRoadSignage"
            continue

        # Rule 2
        if lines == "Yes" and rw == "No" and sign == "No":
            out.at[i, check_col] = "TemporaryLineMarkers present without RoadWorks and Signage"
            continue

    return out


# ----------------------------- Check 5: Illumination ---------------------- #

def check_illumination_consistency(
    df: pd.DataFrame, day_col: str, night_col: str
) -> pd.DataFrame:
    """
    Flag if Day and Night illumination are equal (both Yes or both No).
    Emits EnvironmentalConditions.Illumination_Day_Night_check.
    """
    if day_col not in df.columns or night_col not in df.columns:
        print(f"[warn] check_illumination_consistency: columns not found: {day_col}, {night_col}")
        return df

    out = df.copy()
    colname = "EnvironmentalConditions.Illumination_Day_Night_check"
    out[colname] = "OK"
    valid = out[day_col].notna() & out[night_col].notna()
    bad = valid & (out[day_col] == out[night_col])
    out.loc[bad, colname] = "Illumination inconsistency (Day and Night are the same)"
    return out


# ----------------------------- Check 6: Cloudiness ------------------------ #

def check_cloudiness_scene_switch(
    df: pd.DataFrame,
    scene_col: str,
    clear_col: str,
    partly_col: str,
    overcast_col: str,
) -> pd.DataFrame:
    """
    Within each scene:
      1) Smooth single-step zig-zags per column (Yes/No/Yes → Yes/Yes/Yes).
      2) Enforce exclusivity: exactly one of {Clear, PartlyCloudy, Overcast} == 'Yes'.
         If violated and a previous valid state exists, replace with that state; else flag row.
      3) Disallow direct Clear <-> Overcast transitions unless brief (one-sample detour).
         Must pass through PartlyCloudy otherwise.

    Emits <clear_col>_check with 'OK' or issue text.
    """
    for c in (clear_col, partly_col, overcast_col):
        if c not in df.columns:
            print(f"[warn] check_cloudiness_scene_switch: missing column {c}")
            return df

    out = df.copy()
    check_col = f"{clear_col}_check"
    out[check_col] = "OK"

    for scene_token, group in out.groupby(scene_col):
        idxs = group.index.tolist()

        # Step 1: Zig-zag smoothing (in-place)
        for col in (clear_col, partly_col, overcast_col):
            values = group[col].tolist()
            for i in range(1, len(values) - 1):
                if values[i - 1] == values[i + 1] and values[i] != values[i - 1]:
                    values[i] = values[i - 1]
            out.loc[idxs, col] = values

        # Re-fetch sequences after smoothing
        clear_seq = out.loc[idxs, clear_col].tolist()
        partly_seq = out.loc[idxs, partly_col].tolist()
        overcast_seq = out.loc[idxs, overcast_col].tolist()

        # Step 2: Exclusivity + correction via previous valid state
        state_seq: List[int] = []  # 0=Clear, 1=Partly, 2=Overcast, -1=invalid
        last_valid = None
        for j, row_idx in enumerate(idxs):
            active = {
                0: (clear_seq[j] == "Yes"),
                1: (partly_seq[j] == "Yes"),
                2: (overcast_seq[j] == "Yes"),
            }
            active_count = sum(active.values())

            if active_count == 1:
                # valid
                state = [k for k, v in active.items() if v][0]
                state_seq.append(state)
                last_valid = state
            else:
                if last_valid is not None:
                    # Force to last valid state
                    out.at[row_idx, clear_col] = "Yes" if last_valid == 0 else "No"
                    out.at[row_idx, partly_col] = "Yes" if last_valid == 1 else "No"
                    out.at[row_idx, overcast_col] = "Yes" if last_valid == 2 else "No"
                    state_seq.append(last_valid)
                    out.at[row_idx, check_col] = "OK"
                else:
                    state_seq.append(-1)
                    out.at[row_idx, check_col] = "Cloudiness inconsistency: multiple or none active"

        # Step 3: Transition rule (no direct clear<->overcast unless brief)
        for j in range(1, len(state_seq)):
            prev_state, curr_state = state_seq[j - 1], state_seq[j]
            if prev_state == -1 or curr_state == -1:
                continue
            if abs(curr_state - prev_state) == 2:
                brief = (
                    j >= 2 and j + 1 < len(state_seq)
                    and state_seq[j - 2] == prev_state
                    and state_seq[j + 1] == prev_state
                )
                if not brief:
                    out.at[idxs[j], check_col] = "Clear <-> Overcast must go through PartlyCloudy"

    return out


# ----------------------------- Defaults ----------------------------------- #

DEFAULT_ALLOWED_BASE_COLS = [
    'Scenery.Zones.SchoolZones',
    'Scenery.DrivableArea.DrivableAreaType.Parking',
    'Scenery.DrivableArea.DrivableAreaType.SharedSpace',
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Pavements',
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.BarriersOnEdges',
    'Scenery.DrivableArea.LaneSpecification.LaneNarrow',
    'Scenery.DrivableArea.DrivableAreaEdge.LineMarkers',
    'Scenery.DrivableArea.DrivableAreaEdge.ShoulderPaved',
    'Scenery.DrivableArea.DrivableAreaEdge.ShoulderGrass',
    'Scenery.DrivableArea.DrivableAreaEdge.SolidBarriers',
    'Scenery.DrivableArea.DrivableAreaSurface.SurfaceFeatures.Cracks',
    'Scenery.DrivableArea.DrivableAreaSurface.SurfaceFeatures.Potholes',
    'Scenery.DrivableArea.DrivableAreaSurface.SurfaceFeatures.Ruts',
    'Scenery.DrivableArea.DrivableAreaSurface.Features.Swells',
    'Scenery.DrivableArea.DrivableAreaSurface.InducedSurfaceConditions.StandingWater',
    'Scenery.DrivableArea.DrivableAreaSurface.InducedSurfaceConditions.WetRoad',
    'Scenery.DrivableArea.DrivableAreaSurface.InducedSurfaceConditions.SurfaceContamination',
    'Scenery.SpecialStructures.AutomaticAccessControl',
    'Scenery.SpecialStructures.PedestrianCrossings',
    'Scenery.SpecialStructures.RailCrossings',
    'Scenery.FixedRoadStructures.Buildings',
    'Scenery.FixedRoadStructures.StreetLights',
    'Scenery.FixedRoadStructures.StreetFurniture',
    'Scenery.FixedRoadStructures.Vegetation',
    'Scenery.TemporaryRoadStructures.ConstructionSiteDetours'
]


# ----------------------------- Main --------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description="Semantic scene coherence checks and flags.")
    ap.add_argument("--input", required=True, help="Input CSV with *_Auto_Check columns.")
    ap.add_argument("--output", required=True, help="Output CSV path with *_check columns appended.")
    ap.add_argument("--report", default=None, help="Optional JSON summary report path.")
    ap.add_argument("--scene-col", default="Scene", help="Scene grouping column (default: Scene).")

    # Optional overrides for specific checks
    ap.add_argument("--divided-col", default="Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Divided_Auto_Check")
    ap.add_argument("--undivided-col", default="Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Undivided_Auto_Check")
    ap.add_argument("--lanes-col", default="Scenery.DrivableArea.LaneSpecification.NumberOfLanes_Auto_Check")
    ap.add_argument("--illum-day-col", default="EnvironmentalConditions.Illumination.Day_Auto_Check")
    ap.add_argument("--illum-night-col", default="EnvironmentalConditions.Illumination.Night_Auto_Check")
    ap.add_argument("--cloud-clear-col", default="EnvironmentalConditions.Weather.Cloudiness.Clear_Auto_Check")
    ap.add_argument("--cloud-partly-col", default="EnvironmentalConditions.Weather.Cloudiness.PartlyCloudy_Auto_Check")
    ap.add_argument("--cloud-overcast-col", default="EnvironmentalConditions.Weather.Cloudiness.Overcast_Auto_Check")
    ap.add_argument("--roadworks-col", default="Scenery.TemporaryRoadStructures.RoadWorks_Auto_Check")
    ap.add_argument("--signage-col", default="Scenery.TemporaryRoadStructures.TemporaryRoadSignage_Auto_Check")
    ap.add_argument("--linemarkers-col", default="Scenery.TemporaryRoadStructures.TemporaryLineMarkers_Auto_Check")

    # Signs vs TimeOfOperation pairs (comma-separated pairs "signs_col::time_col;...")
    ap.add_argument("--signs-time-pairs", default=(
        "Scenery.DrivableArea.DrivableAreaSigns.RegulatorySigns.Signs::"
        "Scenery.DrivableArea.DrivableAreaSigns.RegulatorySigns.TimeOfOperation;"
        "Scenery.DrivableArea.DrivableAreaSigns.WarningSigns.Signs::"
        "Scenery.DrivableArea.DrivableAreaSigns.WarningSigns.TimeOfOperation;"
        "Scenery.DrivableArea.DrivableAreaSigns.InformationSigns.Signs::"
        "Scenery.DrivableArea.DrivableAreaSigns.InformationSigns.TimeOfOperation"
    ),
    help='Semicolon-separated "signs::times" pairs (default includes Regulatory/Warning/Information).')

    # Base columns for generic immediate entry/exit toggles (comma-separated)
    ap.add_argument("--base-cols", default=",".join(DEFAULT_ALLOWED_BASE_COLS),
                    help="Comma-separated base columns to process with *_Auto_Check toggles.")
    args = ap.parse_args()

    # Load
    df = pd.read_csv(args.input)
    print(f"[info] Loaded: {args.input} (rows={len(df)}, cols={len(df.columns)})")

    # Parse lists from args
    base_cols = [c.strip() for c in args.base_cols.split(",") if c.strip()]
    pairs: List[Tuple[str, str]] = []
    if args.signs_time_pairs:
        for token in args.signs_time_pairs.split(";"):
            token = token.strip()
            if not token:
                continue
            if "::" in token:
                a, b = token.split("::", 1)
                pairs.append((a.strip(), b.strip()))

    # Apply checks
    df_flags = add_problem_flags(df, args.scene_col, base_cols)
    df_flags = check_divided_undivided_consistency(df_flags, args.divided_col, args.undivided_col)
    df_flags = flag_number_of_lanes(df_flags, args.scene_col, args.lanes_col)
    if pairs:
        df_flags = check_signs_time_pairs(df_flags, pairs)
    df_flags = check_construction_zone(df_flags, args.roadworks_col, args.signage_col, args.linemarkers_col)
    df_flags = check_illumination_consistency(df_flags, args.illum_day_col, args.illum_night_col)
    df_flags = check_cloudiness_scene_switch(
        df_flags, args.scene_col, args.cloud_clear_col, args.cloud_partly_col, args.cloud_overcast_col
    )

    # Save CSV
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df_flags.to_csv(args.output, index=False, encoding="utf-8")
    print(f"[ok] Wrote flagged CSV → {args.output}")

    # Optional report
    if args.report:
        summary: Dict[str, Any] = {"input": args.input, "output": args.output, "rows": len(df_flags), "issues": {}}
        # Count non-OK per *_check column
        for col in df_flags.columns:
            if col.endswith("_check") or col.endswith("_pair_check") or col.endswith("_Undivided_check") or col.endswith("_Day_Night_check"):
                n_bad = int((df_flags[col] != "OK").sum())
                if n_bad > 0:
                    summary["issues"][col] = n_bad
        os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"[ok] Wrote report → {args.report}")


if __name__ == "__main__":
    main()
