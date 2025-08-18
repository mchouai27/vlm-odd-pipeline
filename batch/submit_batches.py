#!/usr/bin/env python3
"""
Iteratively submit, check, and re-submit OpenAI Batch jobs until all outputs are valid JSON.

Workflow:
1. Download results from submitted batches.
2. Split into valid and invalid JSON entries.
3. Create new batch request files for invalid entries.
4. Submit new batches.
5. Repeat until there are no invalid entries left.

Run:
    export OPENAI_API_KEY="sk-..."
    python vlm_integration/iterative_submit_batches.py \
        --base-dir ./Cleaned_results \
        --original-requests ./original_requests.jsonl \
        --initial-ids ./submitted_batch_ids_new.txt
"""

import os
import re
import json
import time
import argparse
import requests
from typing import Dict, Any

BATCH_URL = "https://api.openai.com/v1/batches"
FILES_URL = "https://api.openai.com/v1/files"

_CODE_FENCE_RE = re.compile(r"^```(\w+)?\s*|\s*```$", re.MULTILINE)


def log_message(message: str, log_file_path: str) -> None:
    print(message)
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")


def strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


def check_batch_status(session: requests.Session, batch_id: str) -> Dict[str, Any]:
    url = f"{BATCH_URL}/{batch_id}"
    resp = session.get(url, timeout=60)
    return resp.json() if resp.status_code == 200 else {}


def extract_api_results(session: requests.Session, iteration: int, base_dir: str, headers: Dict[str, str], initial_ids: str | None) -> None:
    """Download batch results for this iteration and separate valid/invalid JSON entries."""
    iteration_folder = os.path.join(base_dir, f"iteration_{iteration}")
    os.makedirs(iteration_folder, exist_ok=True)

    # Iteration 1 can use a special initial IDs file if provided; otherwise use the standard per-iteration file.
    if iteration == 1 and initial_ids and os.path.exists(initial_ids):
        submitted_ids_path = initial_ids
    else:
        submitted_ids_path = os.path.join(iteration_folder, f"submitted_batch_ids_iteration_{iteration}.txt")

    merged_results_path = os.path.join(iteration_folder, f"merged_results_iteration_{iteration}.jsonl")
    invalid_results_path = os.path.join(iteration_folder, f"invalid_results_iteration_{iteration}.jsonl")
    log_path = os.path.join(iteration_folder, "correction_log.txt")

    if not os.path.exists(submitted_ids_path):
        log_message(f"[error] No submitted batch IDs found: {submitted_ids_path}", log_path)
        return

    with open(submitted_ids_path, "r", encoding="utf-8") as f:
        batch_ids = [line.strip() for line in f if line.strip()]

    with open(merged_results_path, "w", encoding="utf-8") as merged_f, open(invalid_results_path, "w", encoding="utf-8") as invalid_f:
        for batch_id in batch_ids:
            batch_info = check_batch_status(session, batch_id)
            status = batch_info.get("status")
            if status != "completed":
                log_message(f"[wait] Batch {batch_id} not completed yet (status={status}). Retrying later.", log_path)
                time.sleep(60)
                continue

            file_id = batch_info.get("output_file_id")
            if not file_id:
                log_message(f"[error] No output_file_id for batch {batch_id}", log_path)
                continue

            file_url = f"{FILES_URL}/{file_id}/content"
            resp = session.get(file_url, timeout=300)
            if resp.status_code != 200:
                log_message(f"[error] Failed to download file {file_id}: {resp.status_code}", log_path)
                continue

            for line in resp.text.splitlines():
                merged_f.write(line + "\n")
                try:
                    result = json.loads(line)
                    # Pull text content; handle code fences; require JSON parse
                    content = result.get("response", {}).get("body", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
                    if isinstance(content, list):
                        text_parts = [blk.get("text", "") for blk in content if isinstance(blk, dict) and blk.get("type") == "text"]
                        content_text = "\n".join(text_parts).strip()
                    else:
                        content_text = str(content).strip()
                    content_text = strip_code_fences(content_text)
                    json.loads(content_text)
                except json.JSONDecodeError:
                    invalid_f.write(line + "\n")

    log_message(f"[ok] Merged results saved to {merged_results_path}", log_path)
    log_message(f"[ok] Invalid results saved to {invalid_results_path}", log_path)


def create_batch_file(iteration: int, base_dir: str, original_requests_path: str, log_path: str) -> None:
    """Create a new batch request file for invalid JSON entries from the previous iteration."""
    iteration_folder = os.path.join(base_dir, f"iteration_{iteration}")
    prev_invalid_path = os.path.join(base_dir, f"iteration_{iteration-1}", f"invalid_results_iteration_{iteration-1}.jsonl")
    batch_request_path = os.path.join(iteration_folder, f"batch_requests_iteration_{iteration}.jsonl")

    if not os.path.exists(prev_invalid_path):
        log_message(f"[warn] Previous invalid file not found: {prev_invalid_path}", log_path)
        return

    with open(original_requests_path, "r", encoding="utf-8") as f:
        original_requests = {}
        for ln in f:
            try:
                obj = json.loads(ln)
                cid = obj.get("custom_id")
                if cid:
                    original_requests[cid] = obj
            except json.JSONDecodeError:
                continue

    written = 0
    missing = 0
    with open(batch_request_path, "w", encoding="utf-8") as batch_f, open(prev_invalid_path, "r", encoding="utf-8") as invalid_f:
        for line in invalid_f:
            try:
                result = json.loads(line)
                cid = result.get("custom_id")
                if cid in original_requests:
                    batch_f.write(json.dumps(original_requests[cid]) + "\n")
                    written += 1
                else:
                    missing += 1
                    log_message(f"[warn] No original request found for custom_id {cid}", log_path)
            except json.JSONDecodeError:
                log_message("[warn] Skipping invalid JSON line in invalid_results file.", log_path)

    log_message(f"[ok] Built next-batch file: {batch_request_path} (written={written}, missing={missing})", log_path)


def submit_batch(session: requests.Session, iteration: int, base_dir: str, headers: Dict[str, str], final_log_path: str) -> None:
    """Upload and submit the batch request file."""
    iteration_folder = os.path.join(base_dir, f"iteration_{iteration}")
    batch_request_path = os.path.join(iteration_folder, f"batch_requests_iteration_{iteration}.jsonl")

    if not os.path.exists(batch_request_path) or os.path.getsize(batch_request_path) == 0:
        log_message(f"[warn] Nothing to submit for iteration {iteration} (missing/empty {batch_request_path}).", final_log_path)
        return

    with open(batch_request_path, "rb") as f:
        files = {"file": (os.path.basename(batch_request_path), f)}
        data = {"purpose": "batch"}
        upload_resp = session.post(FILES_URL, headers=headers, files=files, data=data, timeout=180)

    if upload_resp.status_code != 200:
        log_message(f"[error] Upload failed: {upload_resp.text}", final_log_path)
        return

    file_id = upload_resp.json().get("id")
    batch_data = {"input_file_id": file_id, "endpoint": "/v1/chat/completions", "completion_window": "24h"}
    batch_resp = session.post(BATCH_URL, headers=headers, json=batch_data, timeout=60)

    if batch_resp.status_code == 200:
        batch_id = batch_resp.json().get("id")
        with open(os.path.join(iteration_folder, f"submitted_batch_ids_iteration_{iteration}.txt"), "w", encoding="utf-8") as f:
            f.write(f"{batch_id}\n")
        log_message(f"[ok] Batch submitted: {batch_id}", final_log_path)
    else:
        log_message(f"[error] Batch submission failed: {batch_resp.text}", final_log_path)


def main():
    ap = argparse.ArgumentParser(description="Iteratively submit and re-submit OpenAI batches for invalid JSON correction.")
    ap.add_argument("--base-dir", required=True, help="Base directory to store iteration results.")
    ap.add_argument("--original-requests", required=True, help="Path to original batch requests JSONL.")
    ap.add_argument("--initial-ids", default="submitted_batch_ids_new.txt",
                    help="Initial Batch IDs file used for iteration 1 (default: submitted_batch_ids_new.txt).")
    ap.add_argument("--poll-wait", type=int, default=60, help="Seconds to wait before polling incomplete batches again.")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {api_key}"})

    iteration = 1
    extract_api_results(sess, iteration, args.base_dir, sess.headers, args.initial_ids)

    while True:
        invalid_results_path = os.path.join(args.base_dir, f"iteration_{iteration}", f"invalid_results_iteration_{iteration}.jsonl")
        if os.path.exists(invalid_results_path) and os.path.getsize(invalid_results_path) > 0:
            iteration += 1
            log_path = os.path.join(args.base_dir, f"iteration_{iteration}", "correction_log.txt")
            create_batch_file(iteration, args.base_dir, args.original_requests, log_path)
            submit_batch(sess, iteration, args.base_dir, sess.headers, os.path.join(args.base_dir, "final_correction_log.txt"))
            time.sleep(10)
            extract_api_results(sess, iteration, args.base_dir, sess.headers, args.initial_ids)
        else:
            log_message(f"[done] All JSON entries are valid after iteration {iteration}.", os.path.join(args.base_dir, "final_correction_log.txt"))
            break


if __name__ == "__main__":
    main()
