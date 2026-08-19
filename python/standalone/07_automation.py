"""
07 - Scheduled automation (recurring transfers)
==============================================

Create an automation (a saved/scheduled transfer), then list and inspect it.

Payload shape (mirrors what the web app sends):

  {
    "name": "...", "flowId": "<uuid>",
    "transferType": "no_schedule" | "schedule",
    "timezone": "Asia/Seoul", "callbackURL": null,
    "schedules": [{ "type": "none", "hour": "01", "minute": "00", ... }],
    "details": [{
      "automationDetailId": "", "senderId": "...", "receiverId": "...",
      "step": 1, "fileCount": 1, "folderCount": 0, "sizeCount": 15872,
      "sourceItem": [{ "hash": "<senderId>_ino_<base64url(path)>",
                       "isDir": false, "fileSize": 15872 }],
      "targetPath": "<receiverId>_ino_<base64url(path)>",
      "transferOptions": {"sendFileOption": {}, "targetAction": "numbering"}
    }]
  }

Both sourceItem[].hash and targetPath are device-scoped path references:
  {deviceId}_ino_{base64url(path)}   (see encode_path_ref below)

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  POST   /api/automation
  GET    /api/automation
  GET    /api/automation/{automationId}/details
  POST   /api/automation/pause
  PATCH  /api/automation/{automationId}
  DELETE /api/automation/{automationId}
  GET    /api/device/total-file-and-size-on-path/{deviceId}

Run:
  python 07_automation.py
"""

from __future__ import annotations

import os
import json
import uuid
import base64
import logging
from datetime import datetime, timezone

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
TARGET_PATH = os.getenv("INNORIX_TARGET_PATH", "C:/Users/innorix/Downloads")
SOURCE_PATHS = [p.strip() for p in os.getenv(
    "INNORIX_SOURCE_PATHS", "C:/Users/innorix/Downloads/image").split(",") if p.strip()]

# Whether each source path is a directory (comma-separated true/false, aligned
# with INNORIX_SOURCE_PATHS). Missing entries default to false.
_flags = [v.strip().lower() in ("1", "true", "yes", "y")
          for v in os.getenv("INNORIX_SOURCE_IS_DIR", "").split(",") if v.strip()]
SOURCE_IS_DIR = (_flags + [False] * len(SOURCE_PATHS))[:len(SOURCE_PATHS)]

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("innorix")


# --------------------------------------------------------------------------- #
# Path reference helper: {deviceId}_ino_{base64url(path)}
# --------------------------------------------------------------------------- #
def encode_path_ref(device_id: str, path: str) -> str:
    encoded = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{device_id}_ino_{encoded}"


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

    def total_file_and_size(self, device_id: str, path: str):
        return self._request("GET", f"/api/device/total-file-and-size-on-path/{device_id}",
                             params={"path": path}, timeout=15)

    def create_automation(self, payload: dict):
        return self._request("POST", "/api/automation", json=payload)

    def list_automations(self, page: int = 1, size: int = 20):
        return self._request("GET", "/api/automation",
                             params={"page": page, "size": size}, timeout=10)

    def automation_details(self, automation_id: str):
        return self._request("GET", f"/api/automation/{automation_id}/details", timeout=10)

    def pause_automation(self, pause: bool):
        return self._request("POST", "/api/automation/pause", json={"pause": pause})

    def update_automation(self, automation_id: str, patch: dict):
        return self._request("PATCH", f"/api/automation/{automation_id}", json=patch)

    def delete_automation(self, automation_id: str):
        return self._request("DELETE", f"/api/automation/{automation_id}", timeout=10)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def resolve_size(client, device_id, path):
    """Return (total_size, total_files) for a path, or (0, 0) on failure."""
    try:
        resp = client.total_file_and_size(device_id, path)
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        return int(data.get("totalSize", 0)), int(data.get("totalFiles", 0))
    except Exception as exc:
        print(f"warning: size lookup failed for {path}: {exc}")
        return 0, 0


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # Build source items from the configured paths; sizes come from the device.
    source_item = []
    file_count = folder_count = size_count = 0
    for path, is_dir in zip(SOURCE_PATHS, SOURCE_IS_DIR):
        total_size, total_files = resolve_size(client, SOURCE_ID, path)
        source_item.append({
            "hash": encode_path_ref(SOURCE_ID, path),
            "isDir": is_dir,
            "fileSize": total_size,
        })
        size_count += total_size
        if is_dir:
            folder_count += 1
            file_count += total_files
        else:
            file_count += 1

    detail = {
        "automationDetailId": "",
        "sourceItem": source_item,
        "targetPath": encode_path_ref(TARGET_ID, TARGET_PATH),
        "senderId": SOURCE_ID,
        "receiverId": TARGET_ID,
        "step": 1,
        "fileCount": file_count,
        "folderCount": folder_count,
        "sizeCount": size_count,
        "transferOptions": {"sendFileOption": {}, "targetAction": "numbering"},
    }

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    payload = {
        "name": "Transfer via API example",
        "flowId": str(uuid.uuid4()),
        "details": [detail],
        "transferType": "no_schedule",   # use "schedule" for a recurring job
        "timezone": "Asia/Seoul",
        "callbackURL": None,
        "schedules": [{
            "type": "none", "hour": "01", "minute": "00", "ampm": "am",
            "dayInMonth": 1, "dayInWeek": "monday",
            "startDate": now_iso, "timezone": "Asia/Seoul",
        }],
    }

    created = client.create_automation(payload)
    print(json.dumps(created, indent=2, ensure_ascii=False))

    automation_id = (created.get("data") or {}).get("automationId") \
        or created.get("automationId")
    print("automationId:", automation_id)

    client.list_automations()

    if automation_id:
        client.automation_details(automation_id)
        # client.pause_automation(True)
        # client.update_automation(automation_id, {"name": "renamed"})
        # client.delete_automation(automation_id)


if __name__ == "__main__":
    main()
