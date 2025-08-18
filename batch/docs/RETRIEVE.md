# Collect & Clean Batch Results Across Iterations

This script processes **multiple iterations** of OpenAI Batch results.  
For each iteration, it downloads **completed** batch outputs, writes a merged raw JSONL,  
and produces a cleaned JSON dictionary `{custom_id: parsed_content}`.

All base directories are user-provided — no hardcoded paths.

---

## Requirements

- Python 3.8+
- `requests`

Install:
```bash
pip install requests
````

---

## Usage

```bash
export OPENAI_API_KEY="sk-..."

python collect_iteration_results.py \
  --base-dir Cleaned_results \
  [--overwrite]
```

---

## Arguments

| Flag          | Required | Description                                                                |
| ------------- | -------- | -------------------------------------------------------------------------- |
| `--base-dir`  | Yes      | Path containing `iteration_*` subfolders, each with its own batch ID file. |
| `--overwrite` | No       | Re-process iterations even if result files already exist.                  |

---

## Expected Directory Structure

```
<base-dir>/
  iteration_1/
    submitted_batch_ids_iteration_1.txt
  iteration_2/
    submitted_batch_ids_iteration_2.txt
  ...
```

---

## Output Files (per iteration)

* **`merged_results_<i>.jsonl`**
  Raw per-line JSON objects from the Batch API.

* **`corrected_results_<i>.json`**
  Mapping from `custom_id` to:

  * Parsed JSON object (if valid JSON)
  * Raw string (if JSON parse fails)
  * `{"error": ...}` (if the API returned an error)

Example:

```json
{
  "image_001": { "road_type": "highway", "lanes": 3 },
  "image_002": "Invalid JSON output string",
  "image_003": { "error": { "code": "server_error" } }
}
```

---

## Notes

* Only processes batches with `status="completed"`.
* Skips already processed iterations unless `--overwrite` is set.
* Strips Markdown code fences (` ```json ... ``` `) from model outputs.
* Handles both plain text and structured block formats in message content.

```
```
