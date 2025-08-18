#!/usr/bin/env python3
"""
Collect & clean OpenAI Batch results across all iterations.

Scans a base directory for iteration folders, fetches each completed batch's
output file, writes a per-iteration merged raw JSONL, and builds a cleaned dict
{custom_id: parsed_content_or_raw_text}.

All paths are user-specified via CLI arguments.

Usage:
  export OPENAI_API_KEY="sk-..."
  python vlm_integration/collect_iteration_results.py \
    --base-dir Cleaned_results \
    [--overwrite]

Notes:
  - Iteration layout is expected as:
      <base-dir>/iteration_1/submitted_batch_ids_iteration_1.txt
      <base-dir>/iteration_2/submitted_batch_ids_iteration_2.txt
      ...
  - For each iteration i, this script creates:
      <base-dir>/iteration_i/merged_results_i.jsonl
      <base-dir>/iteration_i/corrected_results_i.json
"""

import os
import re
import json
import argparse
from typing import Dict, Any, Iterable, List, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BATCH_URL = "https://api.openai.com/v1/batches"
FILES_URL = "https://api.openai.com/v1/files"

_CODE_FENCE_RE = re.compile(r"^```(\w+)?\s*|\s*```$", re.MULTILINE)


# ------------------------------- Session ---------------------------------- #

def make_session(api_key: str) -> requests.Session:
    """Create an authenticated session with retries."""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {api_key}"})
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


# ------------------------------- Helpers ---------------------------------- #

def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences like ```json ... ```."""
    return _CODE_FENCE_RE.sub("", text).strip()


def message_content_to_text(msg_content: Any) -> str:
    """Extract text from chat message content (string or list of blocks)."""
    if isinstance(msg_content, str):
        return msg_content
    if isinstance(msg_content, list):
        return "\n".join(
            blk.get("text", "")
            for blk in msg_content
            if isinstance(blk, dict) and blk.get("type") == "text"
        ).strip()
    return str(msg_content)


def get_batch_info(session: requests.Session, batch_id: str) -> Dict[str, Any]:
    """Retrieve batch metadata JSON (or a minimal error dict)."""
    r = session.get(f"{BATCH_URL}/{batch_id}", timeout=60)
    if r.status_code >= 300:
        return {"status": "error", "http": r.status_code, "text": r.text}
    return r.json()


def download_file_lines(session: requests.Session, file_id: str) -> Iterable[str]:
    """Stream lines from a batch output file (JSONL)."""
    url = f"{FILES_URL}/{file_id}/content"
    with session.get(url, timeout=300, stream=True) as r:
        if r.status_code >= 300:
            raise RuntimeError(f"File download failed ({file_id}): {r.status_code} {r.text}")
        for chunk in r.iter_lines(decode_unicode=True):
            if chunk:
                yield chunk


def find_iteration_dirs(base_dir: str) -> List[Tuple[str, str]]:
    """
    Return list of (iteration_dir_path, iteration_index_str) sorted by index,
    e.g., [("<base>/iteration_1","1"), ("<base>/iteration_2","2"), ...]
    """
    out: List[Tuple[str, str]] = []
    if not os.path.isdir(base_dir):
        return out
    for name in os.listdir(base_dir):
        if not name.startswith("iteration_"):
            continue
        idx = name.split("_", 1)[-1]
        if idx.isdigit():
            out.append((os.path.join(base_dir, name), idx))
    out.sort(key=lambda t: int(t[1]))
    return out


# ------------------------------- Core ------------------------------------- #

def process_iteration(session: requests.Session, iteration_dir: str, idx: str, overwrite: bool = False) -> None:
    """
    For a single iteration directory, download completed batch outputs into a merged JSONL,
    and produce a cleaned {custom_id: content} JSON.
    """
    ids_path = os.path.join(iteration_dir, f"submitted_batch_ids_iteration_{idx}.txt")
    merged_path = os.path.join(iteration_dir, f"merged_results_{idx}.jsonl")
    cleaned_path = os.path.join(iteration_dir, f"corrected_results_{idx}.json")

    if not os.path.exists(ids_path):
        print(f"[skip] No batch IDs file for iteration {idx}: {ids_path}")
        return

    if not overwrite and os.path.exists(merged_path) and os.path.exists(cleaned_path):
        print(f"[skip] Iteration {idx} already processed (use --overwrite to redo).")
        return

    with open(ids_path, "r", encoding="utf-8") as f:
        batch_ids = [ln.strip() for ln in f if ln.strip()]
    if not batch_ids:
        print(f"[skip] Empty batch IDs file for iteration {idx}")
        return

    os.makedirs(iteration_dir, exist_ok=True)
    cleaned: Dict[str, Any] = {}
    written_lines = 0

    with open(merged_path, "w", encoding="utf-8") as merged_f:
        for bid in batch_ids:
            info = get_batch_info(session, bid)
            status = info.get("status", "unknown")
            if status != "completed":
                print(f"[wait] iteration {idx}: batch {bid} not completed (status={status}). Skipping.")
                continue

            file_id = info.get("output_file_id")
            if not file_id:
                print(f"[warn] iteration {idx}: batch {bid} missing output_file_id. Skipping.")
                continue

            print(f"[fetch] iteration {idx}: batch {bid} → file {file_id}")
            for line in download_file_lines(session, file_id):
                merged_f.write(line + "\n")
                written_lines += 1

                # Build cleaned mapping
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # keep it in merged; nothing to extract
                    continue

                custom_id = obj.get("custom_id") or "unknown_id"
                # Success path: response.body.choices[0].message.content
                resp = obj.get("response") or {}
                body = resp.get("body") or {}
                choices = body.get("choices") or []

                if choices:
                    content_raw = choices[0].get("message", {}).get("content", "")
                    text = strip_code_fences(message_content_to_text(content_raw))
                    try:
                        cleaned[custom_id] = json.loads(text)  # parsed JSON
                    except Exception:
                        cleaned[custom_id] = text  # keep raw text if not valid JSON
                else:
                    # Error path or unexpected shape
                    err = obj.get("error")
                    cleaned[custom_id] = {"error": err} if err else obj

    with open(cleaned_path, "w", encoding="utf-8") as out_f:
        json.dump(cleaned, out_f, indent=2, ensure_ascii=False)

    print(f"[ok] iteration {idx}: wrote {written_lines} lines → {merged_path}")
    print(f"[ok] iteration {idx}: cleaned outputs → {cleaned_path} (keys={len(cleaned)})")


def main():
    ap = argparse.ArgumentParser(description="Collect & clean OpenAI Batch results across all iterations.")
    ap.add_argument("--base-dir", required=True, help="Base directory containing iteration_* folders.")
    ap.add_argument("--overwrite", action="store_true", help="Re-create merged/cleaned files even if they already exist.")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")
    sess = make_session(api_key)

    iterations = find_iteration_dirs(args.base_dir)
    if not iterations:
        print(f"[info] No iteration_* folders found under {args.base_dir}")
        return

    for iteration_dir, idx in iterations:
        process_iteration(sess, iteration_dir, idx, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
