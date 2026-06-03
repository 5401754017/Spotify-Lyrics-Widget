import base64
import hashlib
import time
from unittest.mock import MagicMock, patch

from src.auth import (
    build_auth_url,
    exchange_code_for_token,
    generate_code_challenge,
    generate_code_verifier,
    is_token_expired,
    refresh_access_token,
)


class TestPKCECrypto:
    def test_code_verifier_length(self):
        verifier = generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_code_verifier_charset(self):
        verifier = generate_code_verifier()
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        assert all(char in allowed for char in verifier)

    def test_code_challenge_is_s256(self):
        verifier = "test_verifier_string_that_is_long_enough_43chars"
        challenge = generate_code_challenge(verifier)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected


class TestBuildAuthUrl:
    def test_contains_required_params(self):
        url = build_auth_url("test_client_id", "test_challenge", "test_state")
        assert "client_id=test_client_id" in url
        assert "code_challenge=test_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url
        assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback" in url
        assert "scope=user-read-currently-playing" in url
        assert "user-read-playback-state" in url
        assert "user-modify-playback-state" in url
        assert "state=test_state" in url


class TestTokenExpiry:
    def test_expired_token(self):
        expires_at = int(time.time()) - 60
        assert is_token_expired(expires_at) is True

    def test_valid_token(self):
        expires_at = int(time.time()) + 3600
        assert is_token_expired(expires_at) is False

    def test_expires_within_buffer(self):
        expires_at = int(time.time()) + 30
        assert is_token_expired(expires_at) is True


class TestExchangeCode:
    @patch("src.auth.httpx.post")
    def test_successful_exchange(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            },
        )
        result = exchange_code_for_token("auth_code", "verifier", "client_id")
        assert result["access_token"] == "new_access"
        assert result["refresh_token"] == "new_refresh"
        assert result["expires_in"] == 3600

    @patch("src.auth.httpx.post")
    def test_failed_exchange_raises(self, mock_post):
        mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
        import pytest

        with pytest.raises(Exception, match="Token exchange failed"):
            exchange_code_for_token("bad_code", "verifier", "client_id")


class TestRefreshToken:
    @patch("src.auth.httpx.post")
    def test_refresh_returns_new_refresh_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_access",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600,
            },
        )
        result = refresh_access_token("old_refresh", "client_id")
        assert result["access_token"] == "refreshed_access"
        assert result["refresh_token"] == "new_refresh_token"

    @patch("src.auth.httpx.post")
    def test_refresh_without_new_refresh_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_access",
                "expires_in": 3600,
            },
        )
        result = refresh_access_token("old_refresh", "client_id")
        assert result["access_token"] == "refreshed_access"
        assert "refresh_token" not in result

    @patch("src.auth.httpx.post")
    def test_refresh_failure_raises(self, mock_post):
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        import pytest

        with pytest.raises(Exception, match="Token refresh failed"):
            refresh_access_token("bad_refresh", "client_id")


def test_has_required_scopes_true_when_all_present():
    from src.auth import has_required_scopes

    granted = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    required = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )

    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_ignores_order_and_extras():
    from src.auth import has_required_scopes

    granted = (
        "extra user-modify-playback-state user-read-playback-state "
        "user-read-currently-playing"
    )
    required = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )

    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_false_when_missing():
    from src.auth import has_required_scopes

    granted = "user-read-currently-playing user-modify-playback-state"
    required = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )

    assert has_required_scopes(granted, required) is False


def test_has_required_scopes_false_when_empty():
    from src.auth import has_required_scopes

    assert has_required_scopes("", "user-read-currently-playing") is False
