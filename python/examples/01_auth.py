"""
01 - Authentication
===================

Log in, inspect the current user, and (optionally) refresh the token.
This is the foundation every other example builds on.

Endpoints:
  POST /api/auth/login
  GET  /api/auth/me
  GET  /api/auth/get-token
  GET  /api/auth/logout

Run:
  python examples/01_auth.py
"""

import json
from _common import make_client


def main() -> None:
    # make_client() already calls login() and sets the auth headers for us.
    client, settings = make_client()

    # Who am I?
    me = client.me()
    print(json.dumps(me, indent=2, ensure_ascii=False))

    # When the access token expires you can either:
    #   - call client.refresh_token(<refresh_token>)  (header X-Refresh-Token)
    #   - or client.get_token()                        (GET /api/auth/get-token)
    # token = client.refresh_token("<REFRESH_TOKEN>")

    # client.logout()  # end the session when you are done


if __name__ == "__main__":
    main()
