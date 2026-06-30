"""Helpers for locating and describing the official local dataset / JD files.

The sandbox runs on the same machine as the dataset, so the official files are
used **in place** — their path is passed straight to the backend ranking
endpoint. Nothing is uploaded through the browser, copied, or read wholly into
memory here (line counting streams the file).
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root = parent of the `sandbox/` package directory.
_ROOT = Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return _ROOT


def official_dataset_path() -> Path:
    """Absolute path to the official candidates.jsonl (env-overridable)."""
    env = os.environ.get("SANDBOX_OFFICIAL_DATASET")
    if env:
        return Path(env).expanduser().resolve()
    return (_ROOT / "dataset" / "candidates.jsonl").resolve()


def official_jd_path() -> Path:
    """Absolute path to the official job_description.docx (env-overridable)."""
    env = os.environ.get("SANDBOX_OFFICIAL_JD")
    if env:
        return Path(env).expanduser().resolve()
    return (_ROOT / "dataset" / "job_description.docx").resolve()


def human_size(num_bytes: int) -> str:
    """Human-readable file size."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def count_jsonl_lines(path: Path) -> int:
    """Count non-empty lines by streaming (never loads the whole file)."""
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count
