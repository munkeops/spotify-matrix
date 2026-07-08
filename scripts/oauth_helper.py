#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_token(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


class CallbackServer:
    def __init__(self, expected_state: str) -> None:
        self.expected_state = expected_state
        self.code: str | None = None
        self.error: str | None = None
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                if parsed.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Wrong callback path.")
                    return
                if params.get("state", [""])[0] != parent.expected_state:
                    parent.error = "Spotify callback state did not match."
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"State mismatch.")
                    return
                if "error" in params:
                    parent.error = f"Spotify authorization failed: {params['error'][0]}"
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Spotify authorization failed.")
                    return
                parent.code = params.get("code", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Spotify Matrix is paired. You can close this tab.")

            def log_message(self, format: str, *args: Any) -> None:
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.redirect_uri = f"http://127.0.0.1:{self.server.server_port}/callback"

    def wait_for_code(self) -> str:
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        try:
            while not self.code and not self.error:
                threading.Event().wait(0.1)
        finally:
            self.server.shutdown()
            self.server.server_close()
        if self.error:
            raise RuntimeError(self.error)
        if not self.code:
            raise RuntimeError("Spotify authorization did not return a code.")
        return self.code


def main() -> None:
    parser = argparse.ArgumentParser(description="Pair Spotify OAuth with a Spotify Matrix Pi.")
    parser.add_argument("--pi", required=True, help="Pi setup UI URL, for example http://raspberrypi.local:3000")
    parser.add_argument("--pairing-token", required=True)
    args = parser.parse_args()

    pi_url = args.pi.rstrip("/")
    session = request_json(f"{pi_url}/api/auth/session/{urllib.parse.quote(args.pairing_token)}")
    state = secrets.token_urlsafe(18)
    callback = CallbackServer(state)
    auth_query = urllib.parse.urlencode(
        {
        'client_id': session['clientId'],
        'response_type': 'code',
        'redirect_uri': callback.redirect_uri,
        'scope': session['scope'],
        'state': state,
        }
    )
    auth_url = f"{AUTH_URL}?{auth_query}"

    print("Opening Spotify authorization URL:")
    print(auth_url)
    webbrowser.open(auth_url)

    code = callback.wait_for_code()
    token = exchange_token(session["clientId"], session["clientSecret"], callback.redirect_uri, code)
    request_json(
        f"{pi_url}/api/token",
        method="POST",
        payload={"pairingToken": args.pairing_token, "token": token},
    )
    print("Spotify token saved to the Pi. You can return to the setup UI.")


if __name__ == "__main__":
    main()
