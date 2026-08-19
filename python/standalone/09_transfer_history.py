"""
09 - Transfer history & CSV report
=================================

Look up the detail and per-file results of a completed transfer, and export the
whole history as CSV for auditing/reporting.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own.

Endpoints:
  GET /api/transfer-history/{id}/detail?idType=monitor
  GET /api/transfer-history/{id}/get-files?idType=monitor
  GET /api/transfer-history/export-csv

Run:
  MONITOR_ID=<monitor_id> python 09_transfer_history.py
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
MONITOR_ID = os.getenv("MONITOR_ID", "<MONITOR_ID>")

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
            return res.text  # e.g. CSV export

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

    def history_detail(self, monitor_id: str, id_type: str = "monitor"):
        return self._request("GET", f"/api/transfer-history/{monitor_id}/detail",
                             params={"idType": id_type}, timeout=10)

    def history_files(self, monitor_id: str, id_type: str = "monitor",
                      page: int = 1, size: int = 20):
        return self._request("GET", f"/api/transfer-history/{monitor_id}/get-files",
                             params={"idType": id_type, "page": page, "size": size}, timeout=10)

    def export_history_csv(self, out_path: str, page: int = 1, size: int = 50, sort=None) -> str:
        params = {"page": page, "size": size}
        if sort:
            params["sort"] = sort
        text = self._request("GET", "/api/transfer-history/export-csv", params=params, timeout=30)
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text if isinstance(text, str) else json.dumps(text))
        log.info("history CSV saved to %s", out_path)
        return out_path


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # Summary of a completed transfer (idType=monitor because we pass a monitorId).
    detail = client.history_detail(MONITOR_ID, id_type="monitor")
    print(json.dumps(detail, indent=2, ensure_ascii=False)[:1000])

    # Per-file results.
    files = client.history_files(MONITOR_ID, id_type="monitor", page=1, size=20)
    print(json.dumps(files, indent=2, ensure_ascii=False)[:1000])

    # Export history as CSV.
    out = client.export_history_csv("transfer_history.csv", page=1, size=50, sort="createdAt:desc")
    print("saved:", out)


if __name__ == "__main__":
    main()
