#!/usr/bin/env python3
"""Export the official validation sample tokens from local nuScenes metadata."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataroot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", default="v1.0-trainval")
    args = parser.parse_args()
    from nuscenes import NuScenes
    from nuscenes.utils.splits import create_splits_scenes

    nusc = NuScenes(version=args.version, dataroot=args.dataroot, verbose=False)
    official_scenes = set(create_splits_scenes()["val"])
    tokens = [sample["token"] for sample in nusc.sample
              if nusc.get("scene", sample["scene_token"])["name"] in official_scenes]
    if args.version == "v1.0-trainval" and len(tokens) != 6019:
        raise ValueError(f"Expected 6019 validation keyframes, got {len(tokens)}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(tokens) + "\n", encoding="utf-8")
    print(f"Exported {len(tokens)} official validation keyframe tokens: {output}")


if __name__ == "__main__":
    main()
