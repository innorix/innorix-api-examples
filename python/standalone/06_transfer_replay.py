"""
06 - Replay a previous transfer
==============================

The replay endpoint has two actions, both shown below:
  action='review' -> return the original transfer's configuration (read-only)
  action='replay' -> start a NEW transfer using that same configuration

A typical flow is: review first to confirm what will be sent, then replay.
The replay response only reports success (data: true); it does NOT return the
new monitorId.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  POST /api/transfer/{monitorId}/replay

Run:
  MONITOR_ID=<previous_monitor_id> python 06_transfer_replay.py
  MONITOR_ID=<previous_monitor_id> DO_REPLAY=1 python 06_transfer_replay.py
"""

from __future__ import annotations

import os
import json
import logging

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_URL = os.getenv("INNORIX_BASE_URL", "https://app.innorix.com")
WORKSPACE_ID = os.getenv("INNORIX_WORKSPACE_ID", "<WORKSPACE_ID>")
EMAIL = os.getenv("INNORIX_EMAIL", "<YOUR_EMAIL>")
PASSWORD = os.getenv("INNORIX_PASSWORD", "<YOUR_PASSWORD>")
MONITOR_ID = os.getenv("MONITOR_ID", "<PREVIOUS_MONITOR_ID>")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("innorix")


# --------------------------------------------------------------------------- #
# Minimal client
# --------------------------------------------------------------------------- #
class ApiError(RuntimeError):
    """Raised when the API returns a non-2xx response."""


class InnorixClient:
    def __init__(self, base_url: str, workspace_id: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method: str, path: str, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        res = self.session.request(method, f"{self.base_url}{path}", **kwargs)
        try:
            res.raise_for_status()
        except requests.HTTPError as exc:
            raise ApiError(f"{method} {path} -> {res.status_code}: {res.text[:500]}") from exc
        if not res.content:
            return None
        try:
            return res.json()
        except ValueError:
            return res.text

    def login(self, email: str, password: str) -> str:
        data = self._request("POST", "/api/auth/login",
                             json={"email": email, "password": password}, timeout=10)
        token = data["data"]["user"]["accessToken"]
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "x-workspace-id": self.workspace_id,
            "Content-Type": "application/json",
        })
        log.info("logged in")
        return token

    def replay(self, monitor_id: str, action: str = "replay"):
        """
        POST /api/transfer/{monitorId}/replay.
        action='review' -> return the original transfer configuration
        action='replay' -> start a new transfer with that configuration
        """
        return self._request("POST", f"/api/transfer/{monitor_id}/replay",
                             json={"action": action})


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # 1) review: inspect the configuration of the original transfer (no side effect).
    config = client.replay(MONITOR_ID, action="review")
    print("[review] original transfer configuration:")
    print(json.dumps(config, indent=2, ensure_ascii=False)[:1000])

    # 2) replay: start a new transfer with that configuration (opt-in).
    if os.getenv("DO_REPLAY") == "1":
        result = client.replay(MONITOR_ID, action="replay")
        print("[replay] result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        ok = bool(result.get("data")) if isinstance(result, dict) else False
        print("replay started successfully" if ok else "replay did not succeed")
    else:
        print("\n(set DO_REPLAY=1 to actually replay and start a new transfer)")


if __name__ == "__main__":
    main()
