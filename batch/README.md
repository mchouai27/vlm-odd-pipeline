# OpenAI Batch Result Correction & Resubmission

This utility automates **downloading**, **validating**, and **resubmitting** JSONL batch jobs from the OpenAI API until all responses are valid JSON.

- **Input**:
  1. `original_requests.jsonl` — the original request file (one JSON object per line, with `custom_id`).
  2. `submitted_batch_ids_iteration_X.txt` — batch IDs from previous submissions.

- **Output**:
  - Merged results for each iteration.
  - Invalid JSON entries isolated for resubmission.
  - New batch jobs submitted until all entries are valid.

---

## Script

- `submit_batches.py` –  
  Downloads results for submitted batch IDs, merges them, extracts invalid JSON outputs, rebuilds requests from the original file, submits new batches, and repeats the process until no invalid JSON remains.

### Why use it?

- Automatically retries only failed entries from large batch jobs.
- Works within **200 MB** / **50,000 requests** batch API limits.
- Tracks iterations, keeping logs and outputs organized.
- Stops automatically when all entries are valid.

---

## Requirements

- Python 3.8+
- `requests` (HTTP client)

Install:

```bash
pip install requests
````

Set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

> **Note:** The script loads the API key from the environment; do **not** hard-code keys.

---

## Expected JSONL Format

Your `original_requests.jsonl` must contain **one request per line** targeting `/v1/chat/completions` and include a `custom_id` field to match failed results back to their original request.

Example:

```json
{
  "custom_id": "sceneToken__sampleToken",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "..." }
        ]
      }
    ]
  }
}
```

---

## Usage

Run:

```bash
python submit_batches.py \
    --base-dir ./Cleaned_results \
    --original-requests ./original_requests.jsonl
```

The script will:

1. **Download results** for the current iteration.
2. **Separate invalid JSON** into `invalid_results_iteration_X.jsonl`.
3. **Rebuild requests** for failed items from `original_requests.jsonl`.
4. **Submit a new batch** for the next iteration.
5. **Repeat** until all entries are valid.

---

## Directory Structure

```
Cleaned_results/
├── iteration_1/
│   ├── submitted_batch_ids_iteration_1.txt
│   ├── merged_results_iteration_1.jsonl
│   ├── invalid_results_iteration_1.jsonl
│   └── correction_log.txt
├── iteration_2/
│   └── ...
└── final_correction_log.txt
```

---

## Outputs

* **Merged Results** — `merged_results_iteration_X.jsonl` contains all results from that iteration.
* **Invalid Results** — `invalid_results_iteration_X.jsonl` contains only malformed JSON entries.
* **Batch Requests** — `batch_requests_iteration_X.jsonl` is created for re-submission.
* **Logs** — Each iteration gets its own `correction_log.txt`, plus a `final_correction_log.txt` when the process completes.

---

## Tracking / Inspecting Batches

Check a batch status:

```bash
curl https://api.openai.com/v1/batches/BATCH_ID \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

List recent batches:

```bash
curl "https://api.openai.com/v1/batches?limit=20" \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## Tips & Troubleshooting

* **401/403 errors** → Check your `OPENAI_API_KEY` environment variable.
* **Malformed JSON** → Ensure all lines in `original_requests.jsonl` are valid JSON objects with `custom_id`.
* **Slow downloads** → The script waits and retries if a batch is not yet complete.

---


