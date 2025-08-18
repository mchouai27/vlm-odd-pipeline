#!/usr/bin/env python3
"""
Build JSONL batch requests for VLM processing of nuScenes frames.

Each line in the output JSONL is a POST /v1/chat/completions payload that includes:
  - a text prompt (augmented with country + driving side for the scene)
  - up to N base64-encoded images from selected camera views

Usage (example):
  python data_extraction/build_jsonl_requests.py \
      --dataroot /path/to/nuscenes \
      --version v1.0-trainval \
      --prompt-path prompt.txt \
      --out original_requests.jsonl \
      --cameras CAM_FRONT_LEFT CAM_FRONT CAM_FRONT_RIGHT \
      --insert-after "- CAM_FRONT_RIGHT "
"""

import argparse
import base64
import json
import os
from typing import Dict, Iterable, List, Tuple

try:
    from tqdm import tqdm  # CLI-friendly progress bar
except Exception:  # pragma: no cover
    def tqdm(x, **k):
        return x

from nuscenes.nuscenes import NuScenes


# Location → country and driving side; defaults match nuScenes locations
LOCATION_TO_COUNTRY = {
    "singapore-onenorth": "Singapore",
    "boston-seaport": "the United States of America",
    "singapore-queenstown": "Singapore",
    "singapore-hollandvillage": "Singapore",
}
LOCATION_TO_DRIVINGSIDE = {
    "singapore-onenorth": "left",
    "boston-seaport": "right",
    "singapore-queenstown": "left",
    "singapore-hollandvillage": "left",
}


def load_metadata(dataroot: str, version: str) -> Tuple[List[dict], List[dict], List[dict]]:
    """Load scenes, samples, and logs JSON from the nuScenes split."""
    base = os.path.join(dataroot, version)
    with open(os.path.join(base, "scene.json"), "r") as f:
        scenes = json.load(f)
    with open(os.path.join(base, "sample.json"), "r") as f:
        samples = json.load(f)
    with open(os.path.join(base, "log.json"), "r") as f:
        logs = json.load(f)
    return scenes, samples, logs


def make_prompt(prompt_template: str, insert_after: str, country: str, driving_side: str) -> str:
    """Inject location/driving-side info into the prompt right after a sentinel string."""
    if insert_after not in prompt_template:
        raise ValueError(
            f"Sentinel not found in prompt: {insert_after!r}. "
            f"Ensure your prompt contains this exact substring."
        )
    details = (
        f"\n\n. These images were captured in {country}. "
        f"Driving is on the {driving_side} side of the road."
    )
    return prompt_template.replace(insert_after, f"{insert_after}{details}")


def b64_data_url_from_image(path: str) -> str:
    """Read an image and return a base64 data URL (JPEG assumed)."""
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def iter_scene_samples(scenes: List[dict], samples: List[dict]) -> Iterable[Tuple[dict, List[dict]]]:
    """Yield (scene, its_samples_sorted_by_timestamp) for each scene."""
    by_scene: Dict[str, List[dict]] = {}
    for s in samples:
        by_scene.setdefault(s["scene_token"], []).append(s)
    for scene in scenes:
        sc = by_scene.get(scene["token"], [])
        sc.sort(key=lambda x: x["timestamp"])
        yield scene, sc


def build_request(custom_id: str, prompt: str, data_urls: List[str]) -> dict:
    """Construct one OpenAI-style chat+vision request."""
    content = [{"type": "text", "text": prompt}]
    for url in data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": content}],
        },
    }


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dataroot", required=True,
                   help="Path to the nuScenes dataset root (contains the split directory, e.g., v1.0-trainval).")
    p.add_argument("--version", default="v1.0-trainval",
                   help="nuScenes split version (default: v1.0-trainval).")
    p.add_argument("--prompt-path", required=True,
                   help="Path to prompt template text file.")
    p.add_argument("--out", default="original_requests.jsonl",
                   help="Output JSONL file path (default: original_requests.jsonl).")
    p.add_argument("--cameras", nargs="+",
                   default=["CAM_FRONT_LEFT", "CAM_FRONT", "CAM_FRONT_RIGHT"],
                   help="Space-separated camera sensor names to include.")
    p.add_argument("--insert-after", default="- CAM_FRONT_RIGHT ",
                   help="Sentinel substring in prompt where location details are injected.")
    args = p.parse_args(argv)

    # Load prompt
    with open(args.prompt_path, "r") as f:
        prompt_template = f.read()

    # Initialize nuScenes API and raw JSONs
    nusc = NuScenes(version=args.version, dataroot=args.dataroot, verbose=True)
    scenes, samples, logs = load_metadata(args.dataroot, args.version)
    log_by_token = {l["token"]: l for l in logs}

    # Prepare output
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    written = 0

    with open(args.out, "w") as out_f:
        for scene, scene_samples in tqdm(iter_scene_samples(scenes, samples), total=len(scenes), desc="Scenes"):
            if not scene_samples:
                continue

            # Scene context
            log = log_by_token[scene["log_token"]]
            loc = log.get("location", "")
            country = LOCATION_TO_COUNTRY.get(loc, "Unknown")
            driving_side = LOCATION_TO_DRIVINGSIDE.get(loc, "unknown")

            # Prompt with location info
            prompt = make_prompt(prompt_template, args.insert_after, country, driving_side)

            # Samples
            for sample in tqdm(scene_samples, leave=False, desc="Samples"):
                sample_token = sample["token"]
                custom_id = f"{scene['token']}__{sample_token}"

                # Collect base64 data URLs for selected cameras
                data_urls: List[str] = []
                sample_rec = nusc.get("sample", sample_token)
                for cam in args.cameras:
                    cam_token = sample_rec["data"].get(cam)
                    if not cam_token:
                        continue
                    img_path, _, _ = nusc.get_sample_data(cam_token)
                    data_urls.append(b64_data_url_from_image(img_path))

                if not data_urls:  # nothing to send for this sample
                    continue

                req_obj = build_request(custom_id, prompt, data_urls)
                out_f.write(json.dumps(req_obj) + "\n")
                written += 1

    print(f"Wrote {written} requests to {args.out}")


if __name__ == "__main__":
    main()
