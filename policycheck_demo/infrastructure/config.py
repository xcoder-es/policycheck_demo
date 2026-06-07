from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    hf_token: str | None = None
    hf_timeout_seconds: int = 8
    max_csv_bytes: int = 512_000
    max_csv_rows: int = 500


def load_config() -> AppConfig:
    token = os.environ.get("HF_TOKEN")
    return AppConfig(hf_token=token)
