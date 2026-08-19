"""
Configuration loaded from environment variables (and an optional .env file).

Copy .env.example to .env and fill in your own values, or export the same
variables in your shell. Never commit real credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    # Optional: load a .env file if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional
    pass


@dataclass
class Settings:
    base_url: str
    workspace_id: str
    email: str
    password: str
    source_id: str
    target_id: str
    target_path: str
    source_paths: list[str]
    source_is_dir: list[bool]


def _split_paths(value: str) -> list[str]:
    """Split a comma-separated path list, ignoring blanks."""
    return [p.strip() for p in value.split(",") if p.strip()]


def _split_bools(value: str, count: int) -> list[bool]:
    """
    Parse a comma-separated true/false list and align it to `count` paths.
    Missing entries default to False; extras are ignored.
    """
    flags = [p.strip().lower() in ("1", "true", "yes", "y") for p in value.split(",") if p.strip()]
    if len(flags) < count:
        flags += [False] * (count - len(flags))
    return flags[:count]


def load_settings() -> Settings:
    """Read all example configuration from the environment."""
    source_paths = _split_paths(
        os.getenv("INNORIX_SOURCE_PATHS", "C:/Users/innorix/Downloads/image")
    )
    return Settings(
        base_url=os.getenv("INNORIX_BASE_URL", "https://app.innorix.com"),
        workspace_id=os.getenv("INNORIX_WORKSPACE_ID", "<WORKSPACE_ID>"),
        email=os.getenv("INNORIX_EMAIL", "<YOUR_EMAIL>"),
        password=os.getenv("INNORIX_PASSWORD", "<YOUR_PASSWORD>"),
        source_id=os.getenv("INNORIX_SOURCE_ID", "<SOURCE_DEVICE_ID>"),
        target_id=os.getenv("INNORIX_TARGET_ID", "<TARGET_DEVICE_ID>"),
        target_path=os.getenv("INNORIX_TARGET_PATH", "C:/Users/innorix/Downloads"),
        source_paths=source_paths,
        source_is_dir=_split_bools(os.getenv("INNORIX_SOURCE_IS_DIR", ""), len(source_paths)),
    )
