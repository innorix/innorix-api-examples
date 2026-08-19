"""
10 - Pre-flight validation
=========================

Reduce transfer failures by validating up front: check the target path, measure
how many files / how much data a path holds, and screen files against the
workspace security policy before sending.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  POST /api/transfer/validation/path
  GET  /api/device/total-file-and-size-on-path/{deviceId}
  POST /api/security-policy/check-transfer-valid

Run:
  python 10_preflight_validation.py
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
TARGET_ID = os.getenv("INNORIX_TARGET_ID", "<TARGET_DEVICE_ID>")
TARGET_PATH = os.getenv("INNORIX_TARGET_PATH", "C:/Users/innorix/Downloads")
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

    def validate_path(self, source_id, target_id, source_items=None, target_path=None):
        body = {"sourceId": source_id, "targetId": target_id}
        if source_items is not None:
            body["sourceItems"] = source_items
        if target_path is not None:
            body["targetPath"] = target_path
        return self._request("POST", "/api/transfer/validation/path", json=body)

    def total_file_and_size(self, device_id: str, path: str):
        return self._request("GET", f"/api/device/total-file-and-size-on-path/{device_id}",
                             params={"path": path}, timeout=15)

    def check_transfer_valid(self, source_id, target_id, sender_files):
        return self._request("POST", "/api/security-policy/check-transfer-valid",
                             json={"sourceId": source_id, "targetId": target_id,
                                   "senderFiles": sender_files})


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # 1) Validate that the source/target and target path are usable.
    path_check = client.validate_path(
        source_id=SOURCE_ID, target_id=TARGET_ID, target_path=TARGET_PATH)
    print("path validation:")
    print(json.dumps(path_check, indent=2, ensure_ascii=False)[:600])

    # 2) How big is what we are about to send?
    size_info = client.total_file_and_size(SOURCE_ID, SOURCE_PATHS[0])
    print("total file/size:")
    print(json.dumps(size_info, indent=2, ensure_ascii=False)[:600])

    # 3) Screen the files against the security policy (sensitive extensions, etc.).
    sender_files = [
        {"name": "report.pdf", "filePath": f"{SOURCE_PATHS[0]}/report.pdf", "type": "file"},
    ]
    policy = client.check_transfer_valid(
        source_id=SOURCE_ID, target_id=TARGET_ID, sender_files=sender_files)
    print("security policy check:")
    print(json.dumps(policy, indent=2, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
