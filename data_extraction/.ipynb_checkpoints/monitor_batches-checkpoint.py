#!/usr/bin/env python3
"""
Monitor OpenAI Batch API jobs.

Reads Batch IDs from a file (one per line), polls their status, and prints a
compact summary that updates only when counts change.

Usage:
  export OPENAI_API_KEY="sk-..."
  python vlm_integration/monitor_batches.py \
    --ids submitted_batch_ids.txt \
    --interval 5 \
    --stop-when-done

Notes:
  - Status buckets:
      * in_progress: ['validating', 'in_progress']
      * completed:   ['completed']
      * other:       any other status or request error
  - Use --list to also print the IDs within each bucket on changes.
"""

import os
import time
import json
import argparse
from typing import Dict, List, Set, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BATCH_URL = "https://api.openai.com/v1/batches"


def make_session(api_key: str) -> requests.Session:
    """Create a requests session with retry/backoff and auth header."""
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def read_ids(path: str) -> List[str]:
    """Read batch IDs (one per line), strip, deduplicate while preserving order."""
    seen: Set[str] = set()
    ids: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            bid = line.strip()
            if not bid or bid in seen:
                continue
            seen.add(bid)
            ids.append(bid)
    if not ids:
        raise ValueError(f"No batch IDs found in {path}.")
    return ids


def get_status(session: requests.Session, batch_id: str) -> str:
    """Return batch status or 'error:<code>' on failure."""
    try:
        r = session.get(f"{BATCH_URL}/{batch_id}", timeout=30)
        if r.status_code >= 300:
            return f"error:{r.status_code}"
        data = r.json()
        # API returns 'status' field such as 'validating', 'in_progress', 'completed', 'failed', etc.
        return data.get("status", "unknown")
    except requests.RequestException:
        return "error:request"


def bucketize(status_by_id: Dict[str, str]) -> Dict[str, List[str]]:
    """Group IDs into in_progress / completed / other."""
    buckets = {"in_progress": [], "completed": [], "other": []}
    for bid, st in status_by_id.items():
        if st in ("validating", "in_progress"):
            buckets["in_progress"].append(bid)
        elif st == "completed":
            buckets["completed"].append(bid)
        else:
            buckets["other"].append(bid)
    return buckets


def print_summary(buckets: Dict[str, List[str]], list_ids: bool = False) -> None:
    """Print a compact summary and optionally the IDs."""
    print("Batch Status Summary:")
    print(f"  In Progress: {len(buckets['in_progress'])}")
    print(f"  Completed:   {len(buckets['completed'])}")
    print(f"  Other:       {len(buckets['other'])}")
    if list_ids:
        if buckets["in_progress"]:
            print("\n[In Progress]")
            for b in buckets["in_progress"]:
                print(f"  - {b}")
        if buckets["completed"]:
            print("\n[Completed]")
            for b in buckets["completed"]:
                print(f"  - {b}")
        if buckets["other"]:
            print("\n[Other]")
            for b in buckets["other"]:
                print(f"  - {b}")
    print("-" * 60)


def main():
    ap = argparse.ArgumentParser(description="Monitor OpenAI Batch API job statuses.")
    ap.add_argument("--ids", required=True, help="Path to file containing Batch IDs (one per line).")
    ap.add_argument("--interval", type=int, default=5, help="Polling interval in seconds (default: 5).")
    ap.add_argument("--list", action="store_true", help="Also list the IDs in each bucket on changes.")
    ap.add_argument("--once", action="store_true", help="Run a single poll and exit.")
    ap.add_argument("--stop-when-done", action="store_true",
                    help="Exit automatically when all batches are completed (and none in 'other').")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set. Export it before running.")

    batch_ids = read_ids(args.ids)
    sess = make_session(api_key)

    last_snapshot: Tuple[int, int, int] = (-1, -1, -1)  # (in_progress, completed, other)

    while True:
        status_by_id: Dict[str, str] = {}
        for bid in batch_ids:
            status_by_id[bid] = get_status(sess, bid)

        buckets = bucketize(status_by_id)
        snapshot = (len(buckets["in_progress"]), len(buckets["completed"]), len(buckets["other"]))

        if snapshot != last_snapshot:
            # Clear screen in terminals; harmless in notebooks
            print("\033c", end="")
            print_summary(buckets, list_ids=args.list)
            last_snapshot = snapshot

        if args.once:
            break

        if args.stop_when_done and snapshot[0] == 0 and snapshot[2] == 0 and snapshot[1] > 0:
            # No in_progress, no other; at least one completed → done
            break

        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
