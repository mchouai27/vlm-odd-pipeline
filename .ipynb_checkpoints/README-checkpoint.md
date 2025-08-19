# VLM ODD Pipeline

End-to-end pipeline to generate, batch, clean, and validate **Operational Design Domain (ODD)** annotations from nuScenes using **Vision-Language Models (VLMs)**.

---

## Pipeline

```mermaid
flowchart LR
  %% Nodes
  NUSC[NuScenes database]
  EXTRACT[make_requests_jsonl.py]
  SUBMIT[submit_batches.py]
  RETRIEVE[retrieve_clean_results.py]
  PREP[preprocess_normalize.py]
  GUI1[review_raw]
  SEM[semantic_scene_consistency.py]
  GUI2[review_flags]
  EXPERT[Expert assessment of traffic sign detection]
  FINAL[Finalize dataset]

  %% Groups (no internal edges)
  subgraph data_extraction
    direction LR
    EXTRACT
  end

  subgraph batch
    direction LR
    SUBMIT
    RETRIEVE
  end

  subgraph processing
    direction LR
    PREP
    SEM
  end

  subgraph ui
    direction LR
    GUI1
    GUI2
  end

  %% Main flow with file-to-file relations
  NUSC --> EXTRACT --> SUBMIT --> RETRIEVE --> PREP --> GUI1 --> SEM --> GUI2 --> FINAL

  %% Additional connection
  NUSC --> EXPERT --> FINAL
````
---

## What’s inside

* **Data extraction** → build `original_requests.jsonl` from nuScenes (3 cameras, base64 images, prompt injection).
* **Batch submission** → submit/monitor via OpenAI Batch API; retrieve results and handle invalid JSON lines iteratively.
* **Result handling** → combined raw JSONL + cleaned map `{custom_id: parsed_json | raw_text | error}`.
* **Preprocessing** → categorical cleanup, lane normalization, rainfall/density mapping (`preprocess_normalize.py`).
* **Semantic checks** → scene-level coherence (toggle spikes, lane jumps, cloudiness transitions, construction logic) (`semantic_scene_consistency.py`).
* **GUIs** → `ui/review_raw` and `ui/review_flags`.

---

## Repository structure

```
.
├─ README.md
├─ requirements.txt
│
├─ configs/
│  └─ prompts/
│     └─ prompt.txt
│
├─ data_extraction/
│  ├─ README.md
│  └─ make_requests_jsonl.py
│
├─ batch/
│  ├─ README.md
│  ├─ collect_iteration_results.py
│  ├─ monitor_batches.py
│  ├─ retrieve_clean_results.py
│  ├─ submit_batches.py
│  └─ docs/
│     ├─ COLLECT.md
│     ├─ MONITORING.md
│     └─ RETRIEVE.md
│
├─ processing/
│  ├─ README.md
│  ├─ preprocess_normalize.py
│  └─ semantic_scene_consistency.py
│
├─ ui/
│  ├─ review_raw/
│  │  ├─ README.md
│  │  ├─ app.py
│  │  ├─ config.json
│  │  ├─ requirements.txt
│  │  ├─ Validation Guide.pdf
│  │  └─ utils.py
│  └─ review_flags/
│     ├─ README.md
│     ├─ app.py
│     ├─ config.json
│     ├─ requirements.txt
│     ├─ Validation Guide.pdf
│     └─ utils.py
│
└─ examples/
   └─ original_requests.example.jsonl
```

---

## Requirements

* Python 3.8+
* Install deps:

```bash
pip install -r requirements.txt
```

Environment:

```bash
export OPENAI_API_KEY="sk-..."   # or load from a .env
```

---

## Quickstart

**0) Download nuScenes (official website)**
Get the **trainval** split and extract locally. You’ll pass `--dataroot` to scripts below.

**1) Build requests JSONL**

```bash
python data_extraction/make_requests_jsonl.py \
  --dataroot /path/to/nuscenes \
  --prompt configs/prompts/prompt.txt \
  --output original_requests.jsonl
```

**2) Submit batches iteratively (generic paths)**

```bash
python batch/submit_batches.py \
  --base-dir <out_dir_for_iterations> \
  --original-requests original_requests.jsonl
```

**3) Monitor batches (generic paths)**

```bash
python batch/monitor_batches.py \
  --ids <path_to_submitted_batch_ids.txt> \
  --stop-when-done
```

**4) Retrieve & clean results**

```bash
# Single IDs file:
python batch/retrieve_clean_results.py \
  --ids <path_to_submitted_batch_ids.txt> \
  --combined <combined_results.jsonl> \
  --cleaned <corrected_results.json>

# Or collect across multiple iterations:
python batch/collect_iteration_results.py \
  --base-dir <out_dir_for_iterations>
```

**5) Automatic preprocessing and normalization**

```bash
python processing/preprocess_normalize.py \
  --input <annotations.csv> \
  --output <cleaned_annotations.csv> \
  --report <checks_report.json>
```

**6) GUI #1 — Manual verification of first sample**

```bash
cd ui/review_raw
pip install -r requirements.txt
streamlit run app.py -- \
  --input <corrected_results.json> \
  --out <raw_overrides.json>
```

* For each scene, manually verify the **first frame** ODD parameters (road type, weather, etc.).
* This is the **temporal anchor** for consistency.

**7) Semantic checks (scene coherence)**

```bash
python processing/semantic_scene_consistency.py \
  --input <cleaned_annotations.csv> \
  --output <with_semantic_flags.csv> \
  --report <semantic_flags_report.json> \
  --scene-col Scene
```

**8) GUI #2 — Manual review of flagged items**

```bash
cd ui/review_flags
pip install -r requirements.txt
streamlit run app.py -- \
  --input <with_semantic_flags.csv> \
  --out <flag_overrides.csv>
```

**9) Finalize dataset**

* Apply overrides from both GUIs to produce the final consistent dataset.

---

## License

MIT (see `LICENSE`).


