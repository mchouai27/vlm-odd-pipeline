# VLM ODD Pipeline

End-to-end pipeline for generating **Vision-Language Model (VLM)** annotations of nuScenes scenes, submitting at scale with the **OpenAI Batch API**, and turning raw outputs into a **clean, normalized, and semantically consistent** dataset.

## What’s inside

- **Data extraction**: build `original_requests.jsonl` from nuScenes (select cameras, base64 images, prompt injection).
- **VLM integration**: prompts in `configs/`, batch submission + monitoring + iterative resubmission on invalid JSON.
- **Result handling**: combined raw JSONL + cleaned `{custom_id: parsed_json|raw_text|error}`.
- **Preprocessing**: categorical cleanup (Yes/No/Maybe), lane normalization, rainfall/density mapping.
- **Semantic checks**: scene-level coherence (toggle spikes, lane jumps, cloudiness transitions, construction logic).
- **GUIs (optional)**: manual review tools for raw outputs and for triaging semantic flags under `ui/`.
- **Notebooks**: runnable examples that mirror the scripts.

## Repo structure

```
vlm-odd-pipeline/
├─ README.md
├─ LICENSE
├─ requirements.txt
├─ .gitignore
├─ .env.example              # OPENAI_API_KEY=...
│
├─ configs/
│  └─ prompts/
│     └─ prompt.txt
│
├─ data_extraction/
│  ├─ make_requests_jsonl.py
│  └─ README.md
│
├─ batch/
│  ├─ submit_batches.py
│  ├─ monitor_batches.py
│  ├─ retrieve_clean_results.py
│  ├─ collect_iteration_results.py     # optional
│  └─ README.md
│
├─ processing/
│  ├─ preprocess_normalize.py
│  └─ semantic_scene_consistency.py
│
├─ ui/                                 # optional GUIs (git submodules recommended)
│  ├─ review_raw/      # GUI #1: manual review of raw corrected JSON
│  └─ review_flags/    # GUI #2: triage rows flagged by semantic checks
│
├─ notebooks/
│  ├─ 01_data_extraction.ipynb
│  ├─ 02_batch_submit_monitor.ipynb
│  ├─ 03_results_retrieval_cleaning.ipynb
│  ├─ 04_preprocess_normalize.ipynb
│  └─ 05_semantic_checks.ipynb
│
└─ examples/
   └─ original_requests.example.jsonl
```

## Requirements

- Python 3.8+
- `pip install -r requirements.txt`

```
requests>=2.32
pandas>=2.2
numpy>=1.26
tqdm>=4.66
nuscenes-devkit>=1.1
```

Set your API key (don’t hard-code it):

```bash
cp .env.example .env   # fill OPENAI_API_KEY
# or
export OPENAI_API_KEY="sk-..."
```

## Quickstart (end-to-end)

1) **Build requests JSONL** from nuScenes:

```bash
python data_extraction/make_requests_jsonl.py   --dataroot /path/to/nuscenes   --prompt configs/prompts/prompt.txt   --output original_requests.jsonl
```

2) **Submit batches iteratively** (creates `Cleaned_results/iteration_*` and resubmits invalids until clean):

```bash
python batch/submit_batches.py   --base-dir Cleaned_results   --original-requests original_requests.jsonl
```

3) **(Optional) Monitor**:

```bash
python batch/monitor_batches.py   --ids Cleaned_results/iteration_1/submitted_batch_ids_iteration_1.txt   --stop-when-done
```

4) **Retrieve + clean** (single IDs file) *or* **collect across iterations**:

```bash
# single IDs file
python batch/retrieve_clean_results.py   --ids submitted_batch_ids.txt   --combined batch_results_combined.jsonl   --cleaned corrected_results.json

# per-iteration walker
python batch/collect_iteration_results.py   --base-dir Cleaned_results   [--overwrite]
```

5) **(Optional) GUI #1 – manual review of raw outputs**:

```bash
cd ui/review_raw
# e.g., streamlit run app.py  (see the GUI's own README for exact arguments)
```

6) **Preprocess & normalize** (CSV):

```bash
python processing/preprocess_normalize.py   --input path/to/annotations.csv   --output cleaned_annotations.csv   --report checks_report.json
```

7) **Semantic scene coherence checks**:

```bash
python processing/semantic_scene_consistency.py   --input merged_flat_data_corrected_auto_check.csv   --output merged_with_semantic_flags.csv   --report semantic_flags_report.json   --scene-col Scene
```

8) **(Optional) GUI #2 – triage flagged rows**:

```bash
cd ui/review_flags
# e.g., streamlit run app.py  (see the GUI's own README for exact arguments)
```

## Key outputs

- `original_requests.jsonl` – one Chat Completions request per line (with base64 images).
- `Cleaned_results/iteration_*/merged_results_*.jsonl` – raw API returns (exact lines).
- `Cleaned_results/iteration_*/corrected_results_*.json` – `{custom_id: parsed|raw|error}`.
- `cleaned_annotations.csv` – normalized CSV (post-processing).
- `merged_with_semantic_flags.csv` – CSV with `_check` columns for inconsistencies.

## Tips

- **Paths**: no hardcoded directories; pass them via CLI.
- **IDs**: every request needs a stable `custom_id` so retries can map back.
- **Git hygiene**: outputs and secrets are ignored by default (`.gitignore`).
- **nuScenes**: install and point `--dataroot` to your local copy; we don’t redistribute data.
- **GUIs as submodules**: add them with
  ```bash
  git submodule add -b main https://github.com/ayush939/Data-Labelling-GUI.git ui/review_raw
  git submodule add -b v2   https://github.com/ayush939/Data-Labelling-GUI.git ui/review_flags
  ```

## License

MIT (see `LICENSE`).

## Citation

If you use this pipeline in research, please cite your accompanying paper/repo.
