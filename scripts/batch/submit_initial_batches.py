#!/usr/bin/env python3
"""Validate, split, and optionally submit the first VLM Batch API requests.

The default prepares local JSONL files only. --execute explicitly enables API
uploads and paid batch creation; a preexisting batch-ID file blocks resubmission.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def split_requests(input_path: Path, output_dir: Path, max_requests: int, max_bytes: int) -> list[Path]:
    if max_requests < 1 or max_bytes < 1:
        raise ValueError("Chunk limits must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    seen: set[str] = set()
    active = None
    count, size = 0, 0
    try:
        with input_path.open("rb") as source:
            for number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    request = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ValueError(f"Invalid JSONL at line {number}") from exc
                if not isinstance(request, dict) or not isinstance(request.get("custom_id"), str) or not request["custom_id"]:
                    raise ValueError(f"Missing custom_id at line {number}")
                if request["custom_id"] in seen:
                    raise ValueError(f"Duplicate custom_id: {request['custom_id']}")
                if request.get("method") != "POST" or request.get("url") != "/v1/chat/completions":
                    raise ValueError(f"Unexpected batch endpoint/method at line {number}")
                body = request.get("body")
                if not isinstance(body, dict) or not isinstance(body.get("model"), str) or not isinstance(body.get("messages"), list):
                    raise ValueError(f"Missing model/messages in request at line {number}")
                payload = line if line.endswith(b"\n") else line + b"\n"
                if len(payload) > max_bytes:
                    raise ValueError(f"Request at line {number} exceeds --max-mib")
                seen.add(request["custom_id"])
                if active is None or count >= max_requests or size + len(payload) > max_bytes:
                    if active is not None:
                        active.close()
                    path = output_dir / f"initial_batch_part_{len(paths) + 1:04d}.jsonl"
                    if path.exists():
                        raise FileExistsError(f"Refusing to overwrite existing chunk: {path}")
                    paths.append(path)
                    active = path.open("wb")
                    count, size = 0, 0
                active.write(payload)
                count += 1
                size += len(payload)
    finally:
        if active is not None:
            active.close()
    if not paths:
        raise ValueError(f"No requests found in {input_path}")
    return paths


def submit(paths: list[Path], ids_path: Path, api_key: str) -> None:
    import requests

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}"})
    # Use exclusive creation to prevent accidentally repeating costly submissions.
    with ids_path.open("x", encoding="utf-8") as ids:
        for path in paths:
            with path.open("rb") as input_file:
                upload = session.post(
                    "https://api.openai.com/v1/files",
                    data={"purpose": "batch"}, files={"file": (path.name, input_file)}, timeout=300,
                )
            if upload.status_code >= 300:
                raise RuntimeError(f"Upload failed for {path.name}: HTTP {upload.status_code}")
            file_id = upload.json().get("id")
            if not file_id:
                raise RuntimeError(f"No file ID returned for {path.name}")
            response = session.post(
                "https://api.openai.com/v1/batches",
                json={"input_file_id": file_id, "endpoint": "/v1/chat/completions", "completion_window": "24h"},
                timeout=90,
            )
            if response.status_code >= 300:
                raise RuntimeError(f"Batch submission failed for {path.name}: HTTP {response.status_code}")
            batch_id = response.json().get("id")
            if not batch_id:
                raise RuntimeError(f"No batch ID returned for {path.name}")
            ids.write(batch_id + "\n")
            ids.flush()
            print(f"Submitted {path.name}: {batch_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Original VLM request JSONL")
    parser.add_argument("--base-dir", required=True, help="Batch output folder")
    parser.add_argument("--max-requests", type=int, default=1000)
    parser.add_argument("--max-mib", type=int, default=50)
    parser.add_argument("--execute", action="store_true", help="Authorize real paid Batch API calls")
    args = parser.parse_args()

    base = Path(args.base_dir)
    first = base / "iteration_1"
    ids_path = first / "submitted_batch_ids_iteration_1.txt"
    if ids_path.exists():
        raise FileExistsError(f"Batch IDs already exist; refusing to resubmit: {ids_path}")
    if args.execute and not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY must be configured for --execute")
    if args.execute:
        paths = split_requests(Path(args.input), first, args.max_requests, args.max_mib * 1024 * 1024)
        print(f"Prepared {len(paths)} batch input files in {first}")
        submit(paths, ids_path, os.environ["OPENAI_API_KEY"])
        print(f"Batch IDs saved in {ids_path}")
    else:
        with tempfile.TemporaryDirectory() as workspace:
            paths = split_requests(Path(args.input), Path(workspace), args.max_requests,
                                   args.max_mib * 1024 * 1024)
            print(f"Validated input; it will create {len(paths)} batch files.")
        print("Dry run: no requests submitted. Add --execute to create local files and submit them.")


if __name__ == "__main__":
    main()
