import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from src.auth import (
    build_auth_url,
    exchange_code_for_token,
    generate_code_challenge,
    generate_code_verifier,
)


CALLBACK_PORT = 8888


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the Spotify OAuth callback."""

    auth_code: str | None = None
    received_state: str | None = None
    error: str | None = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "error" in params:
            _CallbackHandler.error = params["error"][0]
        elif "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            _CallbackHandler.received_state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Authorization complete. You can close this tab.</h1></body></html>"
        )

    def log_message(self, format, *args):
        pass


def run_oauth_flow(client_id: str) -> dict:
    """Run the PKCE browser flow and exchange the callback code for tokens."""
    _CallbackHandler.auth_code = None
    _CallbackHandler.received_state = None
    _CallbackHandler.error = None

    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = secrets.token_urlsafe(16)

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 120

    webbrowser.open(build_auth_url(client_id, challenge, state))
    server.handle_request()
    server.server_close()

    if _CallbackHandler.error:
        raise Exception(f"OAuth error: {_CallbackHandler.error}")
    if _CallbackHandler.auth_code is None:
        raise Exception("No authorization code received")
    if _CallbackHandler.received_state != state:
        raise Exception("OAuth state mismatch - possible CSRF attack")

    return exchange_code_for_token(_CallbackHandler.auth_code, verifier, client_id)
