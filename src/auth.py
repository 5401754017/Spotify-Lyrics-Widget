import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx


SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-currently-playing"

_EXPIRY_BUFFER_SECONDS = 60


def generate_code_verifier() -> str:
    """Generate a random URL-safe PKCE code verifier."""
    return secrets.token_urlsafe(64)[:128]


def generate_code_challenge(verifier: str) -> str:
    """Generate an S256 code challenge from a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_auth_url(client_id: str, code_challenge: str, state: str) -> str:
    """Build the Spotify authorization URL with PKCE parameters."""
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
        "scope": SCOPES,
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def is_token_expired(expires_at: int) -> bool:
    """Return whether a token is expired or inside the refresh buffer."""
    return time.time() >= expires_at - _EXPIRY_BUFFER_SECONDS


def exchange_code_for_token(code: str, code_verifier: str, client_id: str) -> dict:
    """Exchange an authorization code for Spotify tokens."""
    response = httpx.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.status_code} {response.text}")
    return response.json()


def refresh_access_token(refresh_token: str, client_id: str) -> dict:
    """Refresh a Spotify access token."""
    response = httpx.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} {response.text}")
    return response.json()
