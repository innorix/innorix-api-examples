"""
05 - Transfer control & retry
============================

Pause, resume, and cancel an in-flight transfer, and retry only the files that
failed. Control actions are PATCH requests with no body.

Timing note: pause/resume are asynchronous. Send pause only after the transfer
is actually running (status transferring=6), and resume only after the pause
has settled (status transferPause=3). Sending resume too early returns:
    400 "Transfer is already PAUSE_OR_CANCEL cannot excute command"
so we poll for the right state and retry resume a few times.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  PATCH /api/transfer/pause/{monitorId}
  PATCH /api/transfer/resume/{monitorId}
  PATCH /api/transfer/cancel/{monitorId}
  POST  /api/transfer/retry-failed-files

Run:
  python 05_transfer_control.py
"""

from __future__ import annotations

import os
import time
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

TRANSFER_STATUS = {
    -1: "transferQueue", 0: "WaitingTransfer", 1: "StartTransfer",
    2: "transferComplete", 3: "transferPause", 4: "transferError",
    5: "transferCancel", 6: "transferring", 7: "transferSkip",
    8: "transferRetry", 9: "transferPartialComplete", 10: "transferRetryChecking",
    11: "virusScanning", 12: "syncing", 13: "transferInComming",
    14: "transferActivity", 99: "transferFail",
}
TERMINAL_STATES = {2, 4, 5, 9, 99}
TRANSFERRING = 6
RESUMABLE_AFTER_PAUSE = {3}


def status_name(code):
    if code is None:
        return "unknown"
    return TRANSFER_STATUS.get(code, f"unknown({code})")


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

    def create_transfer(self, source_id, target_id, target_path, source_file_paths) -> str:
        body = {
            "sourceId": source_id,
            "targetId": target_id,
            "targetPath": target_path,
            "sourceItem": [{"filePath": p} for p in source_file_paths],
        }
        data = self._request("POST", "/api/transfer/manualTransfer", json=body)
        monitor_id = data["data"]["monitorId"]
        log.info("transfer created monitorId=%s", monitor_id)
        return monitor_id

    def get_detail(self, monitor_id: str) -> dict:
        data = self._request("GET", f"/api/transfer/{monitor_id}/detail-unified",
                             params={"workSpaceId": self.workspace_id}, timeout=10)
        if isinstance(data, dict) and "status" not in data and isinstance(data.get("data"), dict):
            return data["data"]
        return data

    def get_status(self, monitor_id: str):
        raw = self.get_detail(monitor_id).get("status")
        return int(raw) if raw is not None else None

    def wait_for_completion(self, monitor_id: str, interval: float = 3.0) -> int:
        while True:
            status = self.get_status(monitor_id)
            log.info("status=%s(%s)", status, status_name(status))
            if status in TERMINAL_STATES:
                return status
            time.sleep(interval)

    def control(self, monitor_id: str, action: str):
        if action not in {"pause", "resume", "cancel"}:
            raise ValueError(f"unsupported action: {action}")
        result = self._request("PATCH", f"/api/transfer/{action}/{monitor_id}", timeout=10)
        log.info("transfer %s requested monitorId=%s", action, monitor_id)
        print(f"[control:{action}] response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    def retry_failed(self, monitor_id: str, files: list):
        return self._request("POST", "/api/transfer/retry-failed-files",
                             json={"monitorId": monitor_id, "filesRetry": files})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def wait_until(client, monitor_id, target_states, timeout=30.0, interval=1.5):
    """Poll until status is in target_states (or a terminal state) or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get_status(monitor_id)
        if status in target_states or status in TERMINAL_STATES:
            return status
        time.sleep(interval)
    return client.get_status(monitor_id)


def resume_with_retry(client, monitor_id, attempts=5, delay=1.5):
    """Resume, retrying while the server still reports the pause isn't settled."""
    for i in range(attempts):
        try:
            client.control(monitor_id, "resume")
            return True
        except ApiError as exc:  # 400 while state is still settling
            if i == attempts - 1:
                raise
            print(f"resume not ready yet ({exc}); retrying...")
            time.sleep(delay)
    return False


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    monitor_id = client.create_transfer(
        source_id=SOURCE_ID,
        target_id=TARGET_ID,
        target_path=TARGET_PATH,
        source_file_paths=SOURCE_PATHS,
    )
    print("monitorId:", monitor_id)

    # Wait until the transfer is actually running before pausing.
    running = wait_until(client, monitor_id, {TRANSFERRING})
    print("status before pause:", status_name(running))
    if running in TERMINAL_STATES:
        print("transfer finished before it could be paused (too small/fast)")
        return

    client.control(monitor_id, "pause")

    # Wait until the pause has settled before resuming.
    settled = wait_until(client, monitor_id, RESUMABLE_AFTER_PAUSE)
    print("status after pause:", status_name(settled))

    if settled in TERMINAL_STATES:
        print("transfer already finished; nothing to resume")
    else:
        resume_with_retry(client, monitor_id)

        # To cancel instead of resuming:
        # client.control(monitor_id, "cancel")

        final = client.wait_for_completion(monitor_id, interval=3.0)
        print(f"final status: {final} ({status_name(final)})")

        # If the transfer partially failed (status 9), retry just the failed files.
        if final == 9:
            client.retry_failed(monitor_id, [
                {"filePath": "C:/data/export/file.txt", "isFolder": False},
            ])


if __name__ == "__main__":
    main()
