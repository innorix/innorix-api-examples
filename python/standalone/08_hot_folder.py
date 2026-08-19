"""
08 - Hot folders
===============

A hot folder watches a directory on a device so that files placed there are
picked up automatically. This example registers a hot folder, lists them, and
shows how to update/delete one.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  POST   /api/hot-folder
  GET    /api/hot-folder
  GET    /api/hot-folder/{id}
  PATCH  /api/hot-folder/{id}
  DELETE /api/hot-folder/{id}

Run:
  python 08_hot_folder.py
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

    def create_hot_folder(self, device_id: str, path: str):
        return self._request("POST", "/api/hot-folder",
                             json={"deviceId": device_id, "path": path})

    def list_hot_folders(self):
        return self._request("GET", "/api/hot-folder", timeout=10)

    def get_hot_folder(self, hot_folder_id: str):
        return self._request("GET", f"/api/hot-folder/{hot_folder_id}", timeout=10)

    def update_hot_folder(self, hot_folder_id: str, patch: dict):
        return self._request("PATCH", f"/api/hot-folder/{hot_folder_id}", json=patch)

    def delete_hot_folder(self, hot_folder_id: str):
        return self._request("DELETE", f"/api/hot-folder/{hot_folder_id}", timeout=10)


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # Create a hot folder on the source device.
    created = client.create_hot_folder(device_id=SOURCE_ID, path=SOURCE_PATHS[0])
    print(json.dumps(created, indent=2, ensure_ascii=False))

    # List existing hot folders.
    folders = client.list_hot_folders()
    print(json.dumps(folders, indent=2, ensure_ascii=False)[:1000])

    # Update / delete a specific hot folder by its UUID:
    # hot_folder_id = "<HOT_FOLDER_ID>"
    # client.get_hot_folder(hot_folder_id)
    # client.update_hot_folder(hot_folder_id, {"path": "C:/data/new_watch"})
    # client.delete_hot_folder(hot_folder_id)


if __name__ == "__main__":
    main()
