"""Load config.yaml and environment settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    config: dict[str, Any]
    assethub_api_base: str
    assethub_token: str | None
    google_client_secret_file: Path
    google_token_file: Path
    ledger_sheet_id: str | None

    @property
    def output_dir(self) -> Path:
        return ROOT / self.config["output_dir"]


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(ROOT / ".env")
    path = config_path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return Settings(
        config=config,
        assethub_api_base=os.environ.get("ASSETHUB_API_BASE", "https://assethub-api.bigbenett.com"),
        assethub_token=os.environ.get("ASSETHUB_TOKEN") or None,
        google_client_secret_file=ROOT / os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "client_secret.json"),
        google_token_file=ROOT / os.environ.get("GOOGLE_TOKEN_FILE", "token.json"),
        ledger_sheet_id=os.environ.get("LEDGER_SHEET_ID") or None,
    )
