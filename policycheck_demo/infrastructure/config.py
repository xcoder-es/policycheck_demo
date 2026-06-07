from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    hf_token: str | None = None
    hf_timeout_seconds: int = 15
    max_csv_bytes: int = 512_000
    max_csv_rows: int = 500


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def load_config() -> AppConfig:
    token = os.environ.get("HF_TOKEN")
    return AppConfig(hf_token=token, hf_timeout_seconds=_read_int("HF_TIMEOUT_SECONDS", 15))
