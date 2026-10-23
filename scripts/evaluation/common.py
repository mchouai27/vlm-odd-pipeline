"""Small dependency-free utilities for nuScenes-ODD reproduction commands."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def read_csv(path: str | Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"Empty CSV: {path}")
        missing = sorted(set(required) - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Missing columns in {path}: {', '.join(missing)}")
        return list(reader)


def write_csv(path: str | Path, fieldnames: list[str], rows: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: str | Path, content: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_tokens(path: str | Path) -> list[str]:
    """Read JSON list or newline-separated tokens. Fail on duplicate/empty tokens."""
    location = Path(path)
    if location.suffix.lower() == ".json":
        tokens = json.loads(location.read_text(encoding="utf-8"))
    else:
        tokens = [line.strip() for line in location.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not isinstance(tokens, list) or not all(isinstance(t, str) and t.strip() for t in tokens):
        raise ValueError(f"Expected list of nonempty tokens: {path}")
    if len(tokens) != len(set(tokens)):
        raise ValueError(f"Duplicate sample_token found in {path}")
    if not tokens:
        raise ValueError(f"Empty token subset: {path}")
    return tokens


def normalized(value: object) -> str:
    return str(value).strip() if value is not None else ""
