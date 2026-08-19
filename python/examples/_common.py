"""
Shared bootstrap for the examples.

Adds the repo root to sys.path (so ``import innorix`` works when you run a
single example directly), configures logging, and returns a logged-in client.
"""

from __future__ import annotations

import os
import sys
import logging

# Make the top-level ``innorix`` package importable when running e.g.
#   python examples/04_transfer_manual.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from innorix import InnorixClient, load_settings  # noqa: E402


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def make_client(login: bool = True):
    """Return (client, settings). Logs in unless login=False."""
    setup_logging()
    settings = load_settings()
    client = InnorixClient(settings.base_url, settings.workspace_id)
    if login:
        client.login(settings.email, settings.password)
    return client, settings
