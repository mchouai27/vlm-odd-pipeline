# Batch Job Status Monitor

This utility monitors the status of OpenAI **Batch API** jobs and provides a live summary in the terminal or Jupyter notebook.

It is typically used after submitting multiple batch jobs with `submit_batches.py` to track their progress until completion.

---

## Script

- `monitor_batches.py` – Reads a list of Batch IDs, polls their status from the OpenAI Batch API, groups them into status categories, and updates the display whenever counts change.

### Why use it?

- Quickly see how many batches are still running, completed, or in other states.
- Optionally list IDs in each category for debugging.
- Automatically stop when all batches are done.

---

## Requirements

- Python 3.8+
- `requests` (HTTP client)

Install:
```bash
pip install requests
````

---

## Usage

1. **Prepare your Batch IDs file**
   Ensure you have a file (e.g., `submitted_batch_ids.txt`) with one Batch ID per line:

   ```
   batch_abc123
   batch_def456
   batch_xyz789
   ```

2. **Set your API key** (never hard-code it):

   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

3. **Run the script**:

   ```bash
   python vlm_integration/monitor_batches.py \
     --ids submitted_batch_ids.txt \
     --interval 5 \
     --list \
     --stop-when-done
   ```

---

## Arguments

| Flag               | Required | Default | Description                                                                |
| ------------------ | -------- | ------- | -------------------------------------------------------------------------- |
| `--ids`            | Yes      | —       | Path to file containing Batch IDs (one per line).                          |
| `--interval`       | No       | `5`     | Polling interval in seconds.                                               |
| `--list`           | No       | —       | List the IDs in each bucket whenever counts change.                        |
| `--once`           | No       | —       | Poll once and exit.                                                        |
| `--stop-when-done` | No       | —       | Exit automatically when all batches are completed and none are in “other”. |

---

## Status Categories

* **In Progress** → `validating` or `in_progress`
* **Completed** → `completed`
* **Other** → any other status or request error (e.g., `failed`, `expired`, or HTTP error)

---

## Example Output

```
Batch Status Summary:
  In Progress: 5
  Completed:   12
  Other:       0
------------------------------------------------------------
```

With `--list`, IDs are also printed for each category.

---

## Tips

* **Security**: Never commit your API key; use environment variables.
* **Reducing API calls**: Increase `--interval` to poll less frequently.
* **Filtering**: Use `--once` in scripts/CI pipelines to snapshot status without continuous polling.
* **Stop automatically**: Use `--stop-when-done` to end monitoring once everything is complete.

---

## Workflow Integration

Typical end-to-end workflow:

1. **Extract data** with `/data_extraction/` scripts.
2. **Submit batches** with `submit_batches.py`.
3. **Monitor progress** with `monitor_batches.py` until all jobs are complete.
4. **Download results** using the Batch API or a results processing script.

---

