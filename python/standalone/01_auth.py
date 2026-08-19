"""
01 - Authentication
===================

Log in, inspect the current user, and (optionally) refresh the token.
This is the foundation every other example builds on.

This file is self-contained: it embeds a minimal client so it can be read and
run on its own. Fill in the configuration below (or set the matching
INNORIX_* environment variables / .env file).

Endpoints:
  POST /api/auth/login
  GET  /api/auth/me
  GET  /api/auth/get-token
  GET  /api/auth/logout

Run:
  python 01_auth.py
"""

from __future__ import annotations

import os
import json
import logging

import requests

try:  # optional .env support
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

    def refresh_token(self, refresh_token: str) -> str:
        data = self._request("POST", "/api/auth/refresh-token",
                             headers={"X-Refresh-Token": refresh_token}, timeout=10)
        token = data["data"]["user"]["accessToken"]
        self.session.headers["Authorization"] = f"Bearer {token}"
        return token

    def get_token(self):
        return self._request("GET", "/api/auth/get-token", timeout=10)

    def me(self):
        return self._request("GET", "/api/auth/me", timeout=10)

    def logout(self):
        return self._request("GET", "/api/auth/logout", timeout=10)


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> None:
    client = InnorixClient(BASE_URL, WORKSPACE_ID)
    client.login(EMAIL, PASSWORD)

    # Who am I?
    me = client.me()
    print(json.dumps(me, indent=2, ensure_ascii=False))

    # When the access token expires you can either:
    #   - client.refresh_token(<refresh_token>)  (header X-Refresh-Token)
    #   - client.get_token()                     (GET /api/auth/get-token)
    # token = client.refresh_token("<REFRESH_TOKEN>")

    # client.logout()  # end the session when you are done


if __name__ == "__main__":
    main()
