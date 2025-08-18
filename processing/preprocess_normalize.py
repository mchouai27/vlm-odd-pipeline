#!/usr/bin/env python3
"""
preprocess_normalize.py

Automatic Preprocessing (Cleaning) & Normalization for VLM ODD annotations.

What it does:
1) Value cleanup / normalization for noisy categorical fields (Yes/No variants, partials).
2) Lane count normalization (map messy strings to integers).
3) EnvironmentalConditions: Rainfall visibility normalization.
4) Force specific “always No” flags to 'No'.
5) Density normalization (Moderate → Medium).
6) Temporal smoothing (scene-wise) for:
   - Selected Yes/No columns (minimum consecutive rule).
   - NumberOfLanes (remove short spikes).
   - HorizontalPlane (remove short “Straight/Curved” blips; ignore NaNs).

All paths are provided via CLI arguments — no hardcoded directories.

Usage:
  python preprocess_normalize.py \
    --input annotations.csv \
    --output cleaned_annotations.csv \
    --mods-report mods_summary.csv
"""

import os
import json
import argparse
from typing import Any, Dict, List, Tuple

import pandas as pd


# ------------------------------- Config ---------------------------------- #

# 1) Replace 'Yes, No' → 'No' for:
YES_NO_FIX_COLS = [
    "Scenery.Zones.SchoolZones",
    "Scenery.Zones.RegionsOrStates",
    "Scenery.DrivableArea.DrivableAreaType.Parking",
    "Scenery.DrivableArea.DrivableAreaType.DistributorRoads",
]

# 2) 'Yes (partial)' → 'Yes'
SHOULDER_GRASS_COL = "Scenery.DrivableArea.DrivableAreaEdge.ShoulderGrass"

# 3) Replace {'Possible','Maybe'} → 'No' for:
CLEAN_TO_NO_COLS = [
    "Scenery.TemporaryRoadStructures.ConstructionSiteDetours",
    "Scenery.DrivableArea.DrivableAreaSurface.InducedSurfaceConditions.StandingWater",
]

# 4) Lane count normalization
LANE_COL = "Scenery.DrivableArea.LaneSpecification.NumberOfLanes"
LANE_MAP: Dict[str, Any] = {
    "No": 1, "1, No": 1, "2 lanes": 2, "2, No": 2, "2, 3": 2,
    "Two": 2, "two": 2, "3, No": 3, "Multiple": 2, "Multiple lanes": 2,
    "Multiple lanes, No": 2, "Yes": 2, "1 or 2": 2, "n/a, No": 1, "N/A": 1,
    "1.5": 1, "1 lane": 1, "1, Yes": 1, "2, Yes": 2, "Number of Lanes, No": 1,
    "Four": 4, "4, No": 4, "1, Parking": 2, "one": 1,
    "3, including a motorcycle lane": 3, "Three": 3,
}

# 5) Rainfall visibility normalization
RAINFALL_COL = "EnvironmentalConditions.Weather.Rainfall.Visibility"
RAINFALL_MAP = {
    "Light": "LightRain",
    "Moderate": "ModerateRain",
    "LightRain, ModerateRain, HeavyRain": "No",
}

# 6) Force columns to 'No'
SET_TO_NO_COLS = [
    "EnvironmentalConditions.Weather.Snowfall.Visibility",
    "Scenery.SpecialStructures.Tunnels",
    "Scenery.SpecialStructures.TollPlaza",
    "Scenery.DrivableArea.LaneSpecification.LaneType.TramLane",
    "Scenery.DrivableArea.LaneSpecification.LaneType.EmergencyLane",
    "Scenery.DrivableArea.DrivableAreaType.Motorways",
    "Scenery.DrivableArea.DrivableAreaType.RadialRoads",
    "EnvironmentalConditions.Particulates.VolcanicAsh",
    "EnvironmentalConditions.Particulates.SmokeAndPollution",
    "EnvironmentalConditions.Particulates.SandAndDust",
    "EnvironmentalConditions.Particulates.NonPrecipitatingWaterDroplets",
    "EnvironmentalConditions.Particulates.Marine",
    "EnvironmentalConditions.Illumination.ArtificialIllumination",
]

# 8) Density normalization
DENSITY_COL = "DynamicElements.Traffic.DensityOfAgents"

# Scene grouping column (required for sequence smoothing)
SCENE_COL = "Scene"

# Temporal smoothing — allowed Yes/No columns
ALLOWED_YES_NO_COLS = [
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
    'Scenery.DrivableArea.DrivableAreaSurface.Features.Ruts',
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
    'Scenery.TemporaryRoadStructures.ConstructionSiteDetours',
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Divided',
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Undivided',
    'Scenery.TemporaryRoadStructures.RoadWorks',
    'Scenery.TemporaryRoadStructures.TemporaryRoadSignage',
    'Scenery.DrivableArea.DrivableAreaEdge.TemporaryLineMarkers',
    'EnvironmentalConditions.Illumination.Day',
    'EnvironmentalConditions.Illumination.Night',
]

# Per-column min consecutive requirement (default if absent)
MIN_CONSECUTIVE_PER_COL = {
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Divided': 2,
    'Scenery.DrivableArea.DrivableAreaGeometry.TransversePlane.Undivided': 2,
    # everything else uses default_min_consecutive
}
DEFAULT_MIN_CONSECUTIVE = 3

# Horizontal plane column
HORIZONTAL_PLANE_COL = 'Scenery.DrivableArea.DrivableAreaGeometry.HorizontalPlane'


# ----------------------------- Helpers ----------------------------------- #

def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _safe_replace(df: pd.DataFrame, col: str, to_replace, value) -> Tuple[int, float]:
    """Replace values if column exists; return (modified_count, percent_of_rows)."""
    if col not in df.columns:
        return (0, 0.0)
    before = df[col].copy()
    df[col] = df[col].replace(to_replace, value)
    changed = (before != df[col]).sum()
    pct = (changed / max(1, len(df))) * 100.0
    return (int(changed), round(pct, 2))


def _convert_lane_value(x):
    if pd.isna(x):
        return 1  # default to 1 lane for NaN as per given behavior
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        try:
            return int(x)
        except Exception:
            return x
    if x in LANE_MAP:
        return LANE_MAP[x]
    try:
        return int(str(x))
    except Exception:
        return x


def correct_yes_no_sequence(sequence: List[Any], min_consecutive: int = 3) -> List[Any]:
    """
    Smooth short runs in a Yes/No sequence:
      - For any block shorter than min_consecutive that differs from the previous
        block value, flip it to the previous value.
      - First element is trusted; corrections never look back beyond it.
    """
    corrected = list(sequence)
    n = len(corrected)
    i = 1  # start at 1 (first is trusted)
    while i < n:
        curr = corrected[i]
        count = 1
        while (i + count) < n and corrected[i + count] == curr:
            count += 1
        if count < min_consecutive:
            prev_val = corrected[i - 1]
            if curr != prev_val:
                for j in range(i, i + count):
                    corrected[j] = prev_val
                i += count
                continue
        i += count
    return corrected


def correct_number_of_lanes(sequence: List[Any], min_consecutive: int = 3) -> List[Any]:
    """
    Remove short spikes in lane count:
      - If a distinct short block (length < min_consecutive) differs from both neighbors,
        overwrite it with the previous value.
    """
    corrected = list(sequence)
    n = len(corrected)
    i = 0
    while i < n:
        curr = corrected[i]
        count = 1
        while (i + count) < n and corrected[i + count] == curr:
            count += 1
        prev_val = corrected[i - 1] if i > 0 else curr
        next_val = corrected[i + count] if (i + count) < n else curr
        if curr != prev_val and curr != next_val and count < min_consecutive:
            for j in range(i, i + count):
                corrected[j] = prev_val
        i += count
    return corrected


def correct_horizontal_plane(sequence: List[Any], min_consecutive: int = 2) -> List[Any]:
    """
    Correct short 'Straight'/'Curved' blocks. NaNs are ignored.
    If a distinct short block (< min_consecutive) is surrounded by a different value,
    flip it to the previous non-NaN value.
    """
    corrected = list(sequence)
    n = len(corrected)
    i = 0
    while i < n:
        curr = corrected[i]
        if pd.isna(curr):
            i += 1
            continue
        count = 1
        while (i + count) < n and corrected[i + count] == curr:
            count += 1

        prev_val = corrected[i - 1] if i > 0 else curr
        next_val = corrected[i + count] if (i + count) < n else curr
        if pd.isna(prev_val):
            prev_val = curr
        if pd.isna(next_val):
            next_val = curr

        if curr != prev_val and curr != next_val and count < min_consecutive:
            for j in range(i, i + count):
                corrected[j] = prev_val
        i += count
    return corrected


# ------------------------------- Main ------------------------------------ #

def main():
    ap = argparse.ArgumentParser(description="Automatic preprocessing & normalization of VLM ODD annotations.")
    ap.add_argument("--input", required=True, help="Input CSV with annotations.")
    ap.add_argument("--output", required=True, help="Output CSV path for cleaned annotations.")
    ap.add_argument("--mods-report", default=None, help="Optional CSV to summarize modification counts per column.")
    args = ap.parse_args()

    # Load
    df = pd.read_csv(args.input)
    print(f"[info] Loaded {args.input} (rows={len(df)}, cols={len(df.columns)})")
    original = df.copy()
    mods: List[Dict[str, Any]] = []  # for summary reporting

    def _record(col: str, cnt: int, pct: float):
        if cnt > 0:
            mods.append({"Column": col, "Modifications": int(cnt), "Percentage (%)": round(pct, 2)})

    # 1) 'Yes, No' → 'No'
    for col in YES_NO_FIX_COLS:
        cnt, pct = _safe_replace(df, col, "Yes, No", "No")
        _record(col, cnt, pct)

    # 2) 'Yes (partial)' → 'Yes'
    cnt, pct = _safe_replace(df, SHOULDER_GRASS_COL, "Yes (partial)", "Yes")
    _record(SHOULDER_GRASS_COL, cnt, pct)

    # 3) {'Possible','Maybe'} → 'No'
    for col in CLEAN_TO_NO_COLS:
        cnt, pct = _safe_replace(df, col, ["Possible", "Maybe"], "No")
        _record(col, cnt, pct)

    # 4) Lane normalization → integers
    if LANE_COL in df.columns:
        before = df[LANE_COL].copy()
        df[LANE_COL] = df[LANE_COL].apply(_convert_lane_value)
        changed = (before != df[LANE_COL]).sum()
        _record(LANE_COL, int(changed), (changed / max(1, len(df))) * 100.0)
    else:
        print(f"[warn] Lane column not found: {LANE_COL}")

    # 5) Rainfall visibility normalization
    if RAINFALL_COL in df.columns:
        before = df[RAINFALL_COL].copy()
        df[RAINFALL_COL] = df[RAINFALL_COL].replace(RAINFALL_MAP).fillna("No")
        changed = (before != df[RAINFALL_COL]).sum()
        _record(RAINFALL_COL, int(changed), (changed / max(1, len(df))) * 100.0)
    else:
        print(f"[warn] Rainfall column not found: {RAINFALL_COL}")

    # 6) Force specific columns to 'No'
    for col in SET_TO_NO_COLS:
        if col in df.columns:
            before = df[col].copy()
            df[col] = "No"
            changed = (before != df[col]).sum()
            _record(col, int(changed), (changed / max(1, len(df))) * 100.0)

    # 8) Density normalization
    if DENSITY_COL in df.columns:
        before = df[DENSITY_COL].copy()
        df[DENSITY_COL] = df[DENSITY_COL].replace("Moderate", "Medium")
        changed = (before != df[DENSITY_COL]).sum()
        _record(DENSITY_COL, int(changed), (changed / max(1, len(df))) * 100.0)

    # --- Temporal smoothing by Scene --- #
    if SCENE_COL not in df.columns:
        print(f"[warn] Scene column '{SCENE_COL}' not found → skipping temporal smoothing.")
    else:
        # Yes/No smoothing
        for col in ALLOWED_YES_NO_COLS:
            if col not in df.columns:
                continue
            auto_col = f"{col}_Auto_Check"
            df[auto_col] = df[col].copy()
            min_cons = MIN_CONSECUTIVE_PER_COL.get(col, DEFAULT_MIN_CONSECUTIVE)
            changed_total = 0
            for scene in df[SCENE_COL].dropna().unique():
                mask = df[SCENE_COL] == scene
                seq = df.loc[mask, auto_col].tolist()
                corrected = correct_yes_no_sequence(seq, min_consecutive=min_cons)
                changed_total += sum(a != b for a, b in zip(seq, corrected))
                df.loc[mask, auto_col] = pd.Series(corrected, index=df[mask].index)
            if changed_total:
                _record(auto_col, int(changed_total), (changed_total / max(1, len(df))) * 100.0)

        # NumberOfLanes smoothing
        if LANE_COL in df.columns:
            auto_lanes = f"{LANE_COL}_Auto_Check"
            df[auto_lanes] = df[LANE_COL].copy()
            changed_total = 0
            for scene in df[SCENE_COL].dropna().unique():
                mask = df[SCENE_COL] == scene
                seq = df.loc[mask, auto_lanes].tolist()
                corrected = correct_number_of_lanes(seq, min_consecutive=3)
                changed_total += sum(a != b for a, b in zip(seq, corrected))
                df.loc[mask, auto_lanes] = pd.Series(corrected, index=df[mask].index)
            if changed_total:
                _record(auto_lanes, int(changed_total), (changed_total / max(1, len(df))) * 100.0)

        # HorizontalPlane smoothing
        if HORIZONTAL_PLANE_COL in df.columns:
            auto_hp = f"{HORIZONTAL_PLANE_COL}_Auto_Check"
            df[auto_hp] = df[HORIZONTAL_PLANE_COL].copy()
            changed_total = 0
            for scene in df[SCENE_COL].dropna().unique():
                mask = df[SCENE_COL] == scene
                seq = df.loc[mask, auto_hp].tolist()
                corrected = correct_horizontal_plane(seq, min_consecutive=4)
                changed_total += sum(a != b for a, b in zip(seq, corrected))
                df.loc[mask, auto_hp] = pd.Series(corrected, index=df[mask].index)
            if changed_total:
                _record(auto_hp, int(changed_total), (changed_total / max(1, len(df))) * 100.0)

    # Save cleaned CSV
    _ensure_parent_dir(args.output)
    df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"[ok] Cleaned CSV saved → {args.output}")

    # Optional modifications report
    if args.mods_report:
        _ensure_parent_dir(args.mods_report)
        pd.DataFrame(mods).sort_values("Percentage (%)", ascending=False).to_csv(args.mods_report, index=False)
        print(f"[ok] Modifications summary saved → {args.mods_report}")


if __name__ == "__main__":
    main()
