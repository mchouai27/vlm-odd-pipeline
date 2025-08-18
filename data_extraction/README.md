# Data Extraction Scripts

This directory contains Python scripts for extracting nuScenes images and metadata and preparing them for Vision-Language Model (VLM) batch processing.

---

## `build_jsonl_requests.py`

Generates a JSONL file where each line is a POST `/v1/chat/completions` request payload for an OpenAI-compatible VLM (`gpt-4o` in our case).  
Each request includes:

- A **text prompt** (augmented with the country and driving side based on scene metadata)
- Base64-encoded JPEG images from selected camera views

---

### Requirements

- Python 3.8+
- [nuScenes devkit](https://github.com/nutonomy/nuscenes-devkit)
- `tqdm`

Install dependencies:
```bash
pip install nuscenes-devkit tqdm
````

---

### Usage

```bash
python data_extraction/build_jsonl_requests.py \
    --dataroot /path/to/nuscenes \
    --version v1.0-trainval \
    --prompt-path prompt.txt \
    --out original_requests.jsonl \
    --cameras CAM_FRONT_LEFT CAM_FRONT CAM_FRONT_RIGHT \
    --insert-after "- CAM_FRONT_RIGHT "
```

**Arguments:**

| Argument         | Required | Description                                                                                           |
| ---------------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `--dataroot`     | Yes      | Path to your nuScenes dataset root (contains the split directory, e.g., `v1.0-trainval`).             |
| `--version`      | No       | nuScenes split version. Default: `v1.0-trainval`.                                                     |
| `--prompt-path`  | Yes      | Path to the prompt template text file.                                                                |
| `--out`          | No       | Output JSONL file path. Default: `original_requests.jsonl`.                                           |
| `--cameras`      | No       | Space-separated camera sensors to include. Default: `CAM_FRONT_LEFT CAM_FRONT CAM_FRONT_RIGHT`.       |
| `--insert-after` | No       | Sentinel string in the prompt after which location info is inserted. Default: `"- CAM_FRONT_RIGHT "`. |

---

### Output format

Each line in the JSONL contains:

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
          { "type": "text", "text": "<prompt with location info>" },
          { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,<...>" } }
        ]
      }
    ]
  }
}
```

---

### Notes

* The script is **location-agnostic**: you must provide your own `--dataroot` path.
* Images are embedded inline as Base64 data URLs (no external hosting required).
* Samples without any of the selected camera views are skipped.
* The `--insert-after` sentinel must exist in your `prompt.txt`; otherwise, the script will raise an error.

```



