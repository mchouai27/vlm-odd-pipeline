# Build JSONL Requests for VLM (nuScenes)

Script: `data_extraction/make_requests_jsonl.py`  
Generates a **JSONL** file where **each line** is a complete `POST /v1/chat/completions` request for a Vision-Language Model (VLM).  
For every nuScenes sample, it embeds a **text prompt** (augmented with location/driving side) and **base64 images** from selected cameras.

---

## What it does

- Loads **nuScenes** metadata (`scene.json`, `sample.json`, `log.json`) for a given split (default `v1.0-trainval`).
- For each scene → iterates samples (sorted by timestamp).
- Encodes selected camera images as **base64 data URLs** (`data:image/jpeg;base64,...`).
- Injects **country** and **driving side** (left/right) into your prompt **after a sentinel substring**.
- Writes one request per line to `original_requests.jsonl` (or your chosen `--out` path).
- Adds a stable `custom_id` → `sceneToken__sampleToken`.

---

## Usage

```bash
python data_extraction/make_requests_jsonl.py \
  --dataroot /path/to/nuscenes \
  --version v1.0-trainval \
  --prompt-path configs/prompts/prompt.txt \
  --out original_requests.jsonl \
  --cameras CAM_FRONT_LEFT CAM_FRONT CAM_FRONT_RIGHT \
  --insert-after "- CAM_FRONT_RIGHT "
```

### Arguments

| Flag             | Required | Default                                    | Description                                                               |
| ---------------- | -------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| `--dataroot`     | Yes      | —                                          | nuScenes root (contains the split dir like `v1.0-trainval`).              |
| `--version`      | No       | `v1.0-trainval`                            | nuScenes split version.                                                   |
| `--prompt-path`  | Yes      | —                                          | Path to your base prompt `*.txt`.                                         |
| `--out`          | No       | `original_requests.jsonl`                  | Output JSONL path.                                                        |
| `--cameras`      | No       | `CAM_FRONT_LEFT CAM_FRONT CAM_FRONT_RIGHT` | Space-separated camera sensor names to include.                           |
| `--insert-after` | No       | `- CAM_FRONT_RIGHT ` (note trailing space) | **Sentinel** substring in the prompt where location details get injected. |

---

## Prompt injection (important)

The script augments your prompt with:

```
. These images were captured in <Country>. Driving is on the <left|right> side of the road.
```

It **inserts this text right after** the **exact** sentinel substring given by `--insert-after`.
Make sure your prompt **contains** that substring (e.g., a bullet list of cameras):

**Example `prompt.txt` snippet**

```
- CAM_FRONT_LEFT
- CAM_FRONT
- CAM_FRONT_RIGHT 
```

If the sentinel is not present → the script raises a clear error.

Countries/sides are inferred from nuScenes log locations:

* `singapore-*` → Singapore, driving on **left**
* `boston-seaport` → USA, driving on **right**

(Unknown locations are labeled as `Unknown`/`unknown`.)

---

## Output format (one line per request)

Each line is a valid JSON object like:

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
          { "type": "text", "text": "<your prompt with injected location details>" },
          { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
          { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } }
        ]
      }
    ]
  }
}
```

> You can change the `"model"` inside the script if needed.

---

## Tips & troubleshooting

* **No images for a sample?** That sample is skipped (no request written).
* **Large files**: JSONL can get big (base64 images). Split later with your batch submit tool.
* **Validate JSONL** quickly:

  ```bash
  python - <<'PY'
  import json, sys
  ok=0
  for i,l in enumerate(sys.stdin,1):
      try: json.loads(l); ok+=1
      except Exception as e: print(f"line {i}: {e}")
  print("valid lines:", ok)
  PY < original_requests.jsonl
  ```
* **Cameras**: Must match nuScenes sensor keys (e.g., `CAM_FRONT`, `CAM_BACK_LEFT`, etc.).
* **Paths**: No hardcoded dataset paths—always pass `--dataroot`.

---

## Example end-to-end (first steps)

1. Build the request file:

```bash
python data_extraction/make_requests_jsonl.py \
  --dataroot /data/sets/nuscenes \
  --prompt-path configs/prompts/prompt.txt \
  --out original_requests.jsonl
```

2. Submit via your Batch API tooling (see `batch/submit_batches.py` in this repo), then monitor, retrieve, and clean.


::contentReference[oaicite:0]{index=0}
```
