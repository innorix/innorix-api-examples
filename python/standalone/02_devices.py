"""
02 - Devices & connectivity
==========================

List registered devices, find the source/target deviceId, and check whether
each device is online before you attempt a transfer.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  GET /api/device
  GET /api/device/connectivity/{deviceId}
  GET /api/device/{device_id}/detail

Run:
  python 02_devices.py
"""

from __future__ import annotations

import os
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
SOURCE_ID = os.getenv("INNORIX_SOURCE_ID", "<SOURCE_DEVICE_ID>")
TARGET_ID = os.getenv("INNORIX_TARGET_ID", "<TARGET_DEVICE_ID>")

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

    def list_devices(self, page: int = 1, size: int = 20) -> list:
        data = self._request("GET", "/api/device",
                             params={"page": page, "size": size}, timeout=10)
        return data["data"]["devices"]

    def is_online(self, device_id: str) -> bool:
        result = self._request("GET", f"/api/device/connectivity/{device_id}", timeout=10)
        if isinstance(result, dict):
            return bool(result.get("data", result))
        return bool(result)

    def device_detail(self, device_id: str):
        return self._request("GET", f"/api/device/{device_id}/detail", timeout=10)


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    devices = client.list_devices()
    print(f"{len(devices)} device(s) registered:")
    for d in devices:
        name = d.get("deviceName") or d.get("name")
        device_id = d.get("deviceId") or d.get("id")
        print(f"  - {name}  ({device_id})")

    for role, device_id in (("source", SOURCE_ID), ("target", TARGET_ID)):
        online = client.is_online(device_id)
        print(f"{role} {device_id} online={online}")

    # Full detail of one device (uncomment to inspect):
    # import json
    # print(json.dumps(client.device_detail(SOURCE_ID), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
