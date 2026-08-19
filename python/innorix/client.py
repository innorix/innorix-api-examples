"""
Innorix API client
===================

A thin, dependency-light wrapper around the Innorix REST API. Every example
under ``examples/`` uses this single client so that per-request boilerplate
(authentication, headers, error handling) lives in one place.

The full endpoint reference is the Swagger/OpenAPI document:
    https://app.innorix.com/api-docs/
"""

from __future__ import annotations

import json
import time
import base64
import logging
from typing import Any, Optional

import requests

log = logging.getLogger("innorix")


# --------------------------------------------------------------------------- #
# Transfer status codes (must match the server-side enum)
# --------------------------------------------------------------------------- #

TRANSFER_STATUS = {
    -1: "transferQueue",
    0: "WaitingTransfer",
    1: "StartTransfer",
    2: "transferComplete",
    3: "transferPause",
    4: "transferError",
    5: "transferCancel",
    6: "transferring",
    7: "transferSkip",
    8: "transferRetry",
    9: "transferPartialComplete",
    10: "transferRetryChecking",
    11: "virusScanning",
    12: "syncing",
    13: "transferInComming",
    14: "transferActivity",
    99: "transferFail",
}

# States that will not progress on their own -> stop polling.
TERMINAL_STATES = {2, 4, 5, 9, 99}
#   2  transferComplete
#   4  transferError
#   5  transferCancel
#   9  transferPartialComplete
#   99 transferFail

PAUSE_STATE = 3  # not terminal by default (resumable)


def status_name(code: Optional[int]) -> str:
    """Return a human-readable name for a transfer status code."""
    if code is None:
        return "unknown"
    return TRANSFER_STATUS.get(code, f"unknown({code})")


def encode_path_ref(device_id: str, path: str) -> str:
    """
    Build a device-scoped path reference in the format the automation API
    expects for sourceItem / targetPath:

        {deviceId}_ino_{base64url(path)}

    The path is UTF-8 base64url-encoded with the '=' padding stripped.
    Example:
        encode_path_ref("6a6a...", "/Users/innorix/Documents/ios")
        -> "6a6a..._ino_L1VzZXJzL2lubm9yaXgvRG9jdW1lbnRzL2lvcw"
    """
    encoded = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{device_id}_ino_{encoded}"


def decode_path_ref(ref: str) -> tuple[str, str]:
    """Reverse encode_path_ref -> (deviceId, path)."""
    device_id, _, encoded = ref.partition("_ino_")
    pad = "=" * (-len(encoded) % 4)
    path = base64.urlsafe_b64decode(encoded + pad).decode("utf-8")
    return device_id, path



# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class ApiError(RuntimeError):
    """Raised when the API returns a non-2xx response."""


class InnorixClient:
    """Small client wrapping the endpoints used across the examples."""

    def __init__(self, base_url: str, workspace_id: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.session = requests.Session()
        self._access_token: Optional[str] = None

    # -- internal helpers --------------------------------------------------- #

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send a request and return parsed JSON (or raw text / None)."""
        kwargs.setdefault("timeout", self.timeout)
        res = self.session.request(method, self._url(path), **kwargs)
        try:
            res.raise_for_status()
        except requests.HTTPError as exc:
            raise ApiError(f"{method} {path} -> {res.status_code}: {res.text[:500]}") from exc
        if not res.content:
            return None
        try:
            return res.json()
        except ValueError:
            return res.text  # e.g. CSV export

    # -- auth --------------------------------------------------------------- #

    def login(self, email: str, password: str) -> str:
        """POST /api/auth/login -> access token, then set auth headers."""
        data = self._request(
            "POST", "/api/auth/login",
            json={"email": email, "password": password}, timeout=10,
        )
        token = data["data"]["user"]["accessToken"]
        self._set_auth(token)
        log.info("logged in")
        return token

    def _set_auth(self, access_token: str) -> None:
        self._access_token = access_token
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "x-workspace-id": self.workspace_id,
            "Content-Type": "application/json",
        })

    def refresh_token(self, refresh_token: str) -> str:
        """POST /api/auth/refresh-token (header X-Refresh-Token)."""
        data = self._request(
            "POST", "/api/auth/refresh-token",
            headers={"X-Refresh-Token": refresh_token}, timeout=10,
        )
        token = data["data"]["user"]["accessToken"]
        self._set_auth(token)
        log.info("token refreshed")
        return token

    def get_token(self) -> Any:
        """GET /api/auth/get-token -> a new access token."""
        return self._request("GET", "/api/auth/get-token", timeout=10)

    def me(self) -> Any:
        """GET /api/auth/me -> the current authenticated user."""
        return self._request("GET", "/api/auth/me", timeout=10)

    def logout(self) -> Any:
        """GET /api/auth/logout."""
        return self._request("GET", "/api/auth/logout", timeout=10)

    # -- devices ------------------------------------------------------------ #

    def list_devices(self, page: int = 1, size: int = 20) -> list[dict]:
        """GET /api/device -> list of registered devices."""
        data = self._request(
            "GET", "/api/device",
            params={"page": page, "size": size}, timeout=10,
        )
        return data["data"]["devices"]

    def is_online(self, device_id: str) -> bool:
        """GET /api/device/connectivity/{deviceId} -> online?"""
        result = self._request(
            "GET", f"/api/device/connectivity/{device_id}", timeout=10,
        )
        if isinstance(result, dict):
            return bool(result.get("data", result))
        return bool(result)

    def device_detail(self, device_id: str) -> Any:
        """GET /api/device/{device_id}/detail."""
        return self._request("GET", f"/api/device/{device_id}/detail", timeout=10)

    def total_file_and_size(self, device_id: str, path: str) -> Any:
        """GET /api/device/total-file-and-size-on-path/{deviceId}?path=..."""
        return self._request(
            "GET", f"/api/device/total-file-and-size-on-path/{device_id}",
            params={"path": path}, timeout=15,
        )

    # -- file explorer ------------------------------------------------------ #

    def browse(self, device_id: str, path: str, only_folder: bool = False) -> Any:
        """POST /api/explorer/fileSearchV3/{deviceId}."""
        return self._request(
            "POST", f"/api/explorer/fileSearchV3/{device_id}",
            json={"path": path, "onlyFolder": only_folder},
        )

    def create_folder(self, device_id: str, path: str) -> Any:
        """POST /api/explorer/createFolder/{deviceId}."""
        return self._request(
            "POST", f"/api/explorer/createFolder/{device_id}",
            json={"path": path},
        )

    def rename_file(self, device_id: str, path: str, new_name: str) -> Any:
        """POST /api/explorer/renameFile/{deviceId}."""
        return self._request(
            "POST", f"/api/explorer/renameFile/{device_id}",
            json={"path": path, "name": new_name},
        )

    def remove_files(self, device_id: str, list_files: list[str]) -> Any:
        """POST /api/explorer/removeFile/{deviceId}."""
        return self._request(
            "POST", f"/api/explorer/removeFile/{device_id}",
            json={"listFiles": list_files},
        )

    # -- transfer ----------------------------------------------------------- #

    def create_transfer(
        self, source_id: str, target_id: str,
        target_path: str, source_file_paths: list[str],
    ) -> str:
        """POST /api/transfer/manualTransfer -> monitorId."""
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

    def get_detail(self, monitor_id: str, debug: bool = False) -> dict:
        """
        GET /api/transfer/{monitorId}/detail-unified.

        Works for both active and completed transfers. The response carries
        ``status`` (int) and ``percent`` at the top level (no data wrapper).
        """
        data = self._request(
            "GET", f"/api/transfer/{monitor_id}/detail-unified",
            params={"workSpaceId": self.workspace_id}, timeout=10,
        )
        if debug:
            log.info("detail-unified raw:\n%s", json.dumps(data, indent=2, ensure_ascii=False))
        if (isinstance(data, dict) and "status" not in data
                and isinstance(data.get("data"), dict)):
            return data["data"]
        return data

    def get_status(self, monitor_id: str) -> Optional[int]:
        """Return the current transfer status code (int)."""
        raw = self.get_detail(monitor_id).get("status")
        return int(raw) if raw is not None else None

    def wait_for_completion(
        self, monitor_id: str, interval: float = 3.0,
        max_wait: Optional[float] = None, stop_on_pause: bool = False,
    ) -> int:
        """Poll detail-unified until the transfer reaches a terminal state."""
        started = time.monotonic()
        while True:
            detail = self.get_detail(monitor_id)
            raw = detail.get("status")
            status = int(raw) if raw is not None else None
            percent = detail.get("percent")
            log.info(
                "status=%s(%s) percent=%s",
                status, status_name(status),
                f"{percent}%" if percent is not None else "-",
            )
            if status in TERMINAL_STATES:
                return status
            if stop_on_pause and status == PAUSE_STATE:
                return status
            if max_wait is not None and time.monotonic() - started > max_wait:
                raise ApiError(f"timeout: not finished within {max_wait}s")
            time.sleep(interval)

    def control(self, monitor_id: str, action: str) -> Any:
        """PATCH /api/transfer/{pause|resume|cancel}/{monitorId}."""
        if action not in {"pause", "resume", "cancel"}:
            raise ValueError(f"unsupported action: {action}")
        result = self._request("PATCH", f"/api/transfer/{action}/{monitor_id}", timeout=10)
        log.info("transfer %s requested monitorId=%s", action, monitor_id)
        print(f"[control:{action}] response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    def retry_failed(self, monitor_id: str, files: list[dict]) -> Any:
        """POST /api/transfer/retry-failed-files."""
        return self._request(
            "POST", "/api/transfer/retry-failed-files",
            json={"monitorId": monitor_id, "filesRetry": files},
        )

    def replay(self, monitor_id: str, action: str = "replay") -> Any:
        """
        POST /api/transfer/{monitorId}/replay.
        action='review' -> return the original transfer configuration
        action='replay' -> start a new transfer with that configuration
        """
        return self._request(
            "POST", f"/api/transfer/{monitor_id}/replay",
            json={"action": action},
        )

    def validate_path(
        self, source_id: str, target_id: str,
        source_items: Optional[str] = None, target_path: Optional[str] = None,
    ) -> Any:
        """POST /api/transfer/validation/path."""
        body: dict[str, Any] = {"sourceId": source_id, "targetId": target_id}
        if source_items is not None:
            body["sourceItems"] = source_items
        if target_path is not None:
            body["targetPath"] = target_path
        return self._request("POST", "/api/transfer/validation/path", json=body)

    # -- automation --------------------------------------------------------- #

    def generate_automation_name(self) -> Any:
        """GET /api/automation/generateAutomationName."""
        return self._request("GET", "/api/automation/generateAutomationName", timeout=10)

    def create_automation(self, payload: dict) -> Any:
        """POST /api/automation with the full request body -> automation."""
        return self._request("POST", "/api/automation", json=payload)

    def list_automations(self, page: int = 1, size: int = 20) -> Any:
        """GET /api/automation."""
        return self._request(
            "GET", "/api/automation",
            params={"page": page, "size": size}, timeout=10,
        )

    def automation_details(self, automation_id: str) -> Any:
        """GET /api/automation/{automationId}/details."""
        return self._request("GET", f"/api/automation/{automation_id}/details", timeout=10)

    def pause_automation(self, pause: bool) -> Any:
        """POST /api/automation/pause (body {"pause": bool})."""
        return self._request("POST", "/api/automation/pause", json={"pause": pause})

    def update_automation(self, automation_id: str, patch: dict) -> Any:
        """PATCH /api/automation/{automationId}."""
        return self._request("PATCH", f"/api/automation/{automation_id}", json=patch)

    def delete_automation(self, automation_id: str) -> Any:
        """DELETE /api/automation/{automationId}."""
        return self._request("DELETE", f"/api/automation/{automation_id}", timeout=10)

    # -- hot folder --------------------------------------------------------- #

    def create_hot_folder(self, device_id: str, path: str) -> Any:
        """POST /api/hot-folder."""
        return self._request(
            "POST", "/api/hot-folder",
            json={"deviceId": device_id, "path": path},
        )

    def list_hot_folders(self) -> Any:
        """GET /api/hot-folder."""
        return self._request("GET", "/api/hot-folder", timeout=10)

    def get_hot_folder(self, hot_folder_id: str) -> Any:
        """GET /api/hot-folder/{id}."""
        return self._request("GET", f"/api/hot-folder/{hot_folder_id}", timeout=10)

    def update_hot_folder(self, hot_folder_id: str, patch: dict) -> Any:
        """PATCH /api/hot-folder/{id}."""
        return self._request("PATCH", f"/api/hot-folder/{hot_folder_id}", json=patch)

    def delete_hot_folder(self, hot_folder_id: str) -> Any:
        """DELETE /api/hot-folder/{id}."""
        return self._request("DELETE", f"/api/hot-folder/{hot_folder_id}", timeout=10)

    # -- transfer history --------------------------------------------------- #

    def history_detail(self, monitor_id: str, id_type: str = "monitor") -> Any:
        """GET /api/transfer-history/{id}/detail?idType=..."""
        return self._request(
            "GET", f"/api/transfer-history/{monitor_id}/detail",
            params={"idType": id_type}, timeout=10,
        )

    def history_files(self, monitor_id: str, id_type: str = "monitor",
                      page: int = 1, size: int = 20) -> Any:
        """GET /api/transfer-history/{id}/get-files?idType=..."""
        return self._request(
            "GET", f"/api/transfer-history/{monitor_id}/get-files",
            params={"idType": id_type, "page": page, "size": size}, timeout=10,
        )

    def export_history_csv(self, out_path: str, page: int = 1, size: int = 50,
                           sort: Optional[str] = None) -> str:
        """GET /api/transfer-history/export-csv and save to out_path."""
        params: dict[str, Any] = {"page": page, "size": size}
        if sort:
            params["sort"] = sort
        text = self._request("GET", "/api/transfer-history/export-csv",
                             params=params, timeout=30)
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text if isinstance(text, str) else json.dumps(text))
        log.info("history CSV saved to %s", out_path)
        return out_path

    # -- security policy ---------------------------------------------------- #

    def check_transfer_valid(self, source_id: str, target_id: str,
                             sender_files: list[dict]) -> Any:
        """POST /api/security-policy/check-transfer-valid."""
        return self._request(
            "POST", "/api/security-policy/check-transfer-valid",
            json={"sourceId": source_id, "targetId": target_id,
                  "senderFiles": sender_files},
        )
