from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    hf_token: str | None = None
    hf_timeout_seconds: int = 8
    max_csv_bytes: int = 512_000
    max_csv_rows: int = 500



def load_config() -> AppConfig:
    return AppConfig(hf_token=os.getenv("HF_TOKEN"))
