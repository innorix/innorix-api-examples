"""
03 - Remote file explorer
========================

Browse a source device's filesystem and manage folders remotely: create,
rename, and delete. Useful when you need to discover the exact file paths to
transfer instead of hard-coding them.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  POST /api/explorer/fileSearchV3/{deviceId}
  POST /api/explorer/createFolder/{deviceId}
  POST /api/explorer/renameFile/{deviceId}
  POST /api/explorer/removeFile/{deviceId}

Run:
  python 03_explorer.py
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
SOURCE_ID = os.getenv("INNORIX_SOURCE_ID", "<SOURCE_DEVICE_ID>")
SOURCE_PATHS = [p.strip() for p in os.getenv(
    "INNORIX_SOURCE_PATHS", "C:/Users/innorix/Downloads/image").split(",") if p.strip()]

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

    def browse(self, device_id: str, path: str, only_folder: bool = False):
        """POST /api/explorer/fileSearchV3/{deviceId}."""
        return self._request("POST", f"/api/explorer/fileSearchV3/{device_id}",
                             json={"path": path, "onlyFolder": only_folder})

    def create_folder(self, device_id: str, path: str):
        return self._request("POST", f"/api/explorer/createFolder/{device_id}",
                             json={"path": path})

    def rename_file(self, device_id: str, path: str, new_name: str):
        return self._request("POST", f"/api/explorer/renameFile/{device_id}",
                             json={"path": path, "name": new_name})

    def remove_files(self, device_id: str, list_files: list):
        return self._request("POST", f"/api/explorer/removeFile/{device_id}",
                             json={"listFiles": list_files})


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    device_id = SOURCE_ID
    base = SOURCE_PATHS[0]

    # 1) Browse a path (set only_folder=True to list folders only).
    listing = client.browse(device_id, base, only_folder=False)
    print(json.dumps(listing, indent=2, ensure_ascii=False)[:1000])

    # --- The mutating calls below are commented out on purpose. -------------
    # Uncomment and adjust paths to actually create/rename/delete on the device.

    # 2) Create a folder.
    # client.create_folder(device_id, f"{base}/example_new_folder")

    # 3) Rename it (path = current path, name = new leaf name).
    # client.rename_file(device_id, f"{base}/example_new_folder", "renamed_folder")

    # 4) Remove files/folders (listFiles = absolute paths).
    # client.remove_files(device_id, [f"{base}/renamed_folder"])


if __name__ == "__main__":
    main()
