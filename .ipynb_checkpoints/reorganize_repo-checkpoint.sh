#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash reorganize_repo.sh                # use current dir as project root
#   bash reorganize_repo.sh /path/to/root  # or pass the project root explicitly

PROJECT_ROOT="${1:-$PWD}"

echo ">> project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

echo ">> creating target folders"
mkdir -p configs/prompts batch/docs processing notebooks examples .github/workflows

# ---------- helpers ----------
mv_if_exists() {
  local from="$1"
  local to="$2"
  if [ -f "$from" ]; then
    mkdir -p "$(dirname "$to")"
    mv -v "$from" "$to"
  else
    echo "skip (not found): $from"
  fi
}

write_if_missing() {
  local path="$1"
  shift
  if [ ! -f "$path" ]; then
    mkdir -p "$(dirname "$path")"
    cat >"$path" <<'EOF'
'"$@"'
EOF
    echo "created: $path"
  else
    echo "keep (exists): $path"
  fi
}

# ---------- data_extraction ----------
mv_if_exists "data_extraction/build_jsonl_requests.py" "data_extraction/make_requests_jsonl.py"
# keep existing data_extraction/README.md

# ---------- batch utilities (move out of data_extraction/) ----------
mv_if_exists "data_extraction/monitor_batches.py"        "batch/monitor_batches.py"
mv_if_exists "data_extraction/retrieve_clean_results.py" "batch/retrieve_clean_results.py"
mv_if_exists "data_extraction/submit_batches.py"         "batch/submit_batches.py"
# optional/if present
mv_if_exists "data_extraction/collect_iteration_results.py" "batch/collect_iteration_results.py"

# docs with spaces → normalize
mv_if_exists "data_extraction/Read me submit batches.md" "batch/README.md"
mv_if_exists "data_extraction/read me Monotoring.md"     "batch/docs/MONITORING.md"
mv_if_exists "data_extraction/Retrieve.md"               "batch/docs/RETRIEVE.md"

# ---------- processing (from vlm_integration/) ----------
mv_if_exists "vlm_integration/preprocess_normalize.py"       "processing/preprocess_normalize.py"
mv_if_exists "vlm_integration/semantic_scene_consistency.py" "processing/semantic_scene_consistency.py"
mv_if_exists "vlm_integration/structure_env_scenery.py"      "processing/structure_env_scenery.py"

# remove empty dir if empty
rmdir "vlm_integration" 2>/dev/null || true

# ---------- boilerplate / starter files ----------
write_if_missing ".env.example" '# copy to .env and fill in
OPENAI_API_KEY='

write_if_missing "requirements.txt" 'requests>=2.32
pandas>=2.2
numpy>=1.26
tqdm>=4.66
nuscenes-devkit>=1.1'

write_if_missing ".gitignore" '# venv
.venv/
# secrets
.env
# data/outputs
Cleaned_results/
split_batches/
*.jsonl
*.csv
*.parquet
# notebooks
.ipynb_checkpoints/
# OS/IDE
.DS_Store
.vscode/'

write_if_missing "configs/prompts/prompt.txt" '# base VLM prompt goes here'

write_if_missing "examples/original_requests.example.jsonl" '{"custom_id":"scene__sample","method":"POST","url":"/v1/chat/completions","body":{"model":"gpt-4o","messages":[{"role":"user","content":[{"type":"text","text":"..."}]}]}}'

write_if_missing "README.md" '# VLM ODD Pipeline

End-to-end pipeline:
1) data_extraction/make_requests_jsonl.py
2) batch/submit_batches.py + batch/monitor_batches.py
3) batch/retrieve_clean_results.py or batch/collect_iteration_results.py
4) processing/preprocess_normalize.py
5) processing/structure_env_scenery.py
6) processing/semantic_scene_consistency.py

## setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill OPENAI_API_KEY
'

write_if_missing "batch/README.md" '# Batch Utilities
- submit_batches.py – iterative correction & resubmission
- monitor_batches.py – live status summary
- retrieve_clean_results.py – combined raw JSONL + cleaned dict
- collect_iteration_results.py – iterate folders and clean results
'

write_if_missing "processing/README.md" '# Processing
- preprocess_normalize.py – CSV cleanup & normalization
- structure_env_scenery.py – fix/move EnvironmentalConditions & Scenery keys
- semantic_scene_consistency.py – temporal/semantic checks across scenes
'

write_if_missing ".github/workflows/lint.yml" 'name: lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: python -m pip install --upgrade pip ruff
      - run: ruff check .
'

# optional empty notebooks as placeholders
touch notebooks/01_data_extraction.ipynb \
      notebooks/02_batch_submit_monitor.ipynb \
      notebooks/03_results_retrieval_cleaning.ipynb \
      notebooks/04_preprocess_normalize.ipynb \
      notebooks/05_semantic_checks.ipynb

echo ">> final tree (max depth 3)"
find . -maxdepth 3 -type d -print | sort
echo "✅ done."
