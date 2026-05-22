from unittest.mock import patch

from src.auth_server import CALLBACK_PORT, _CallbackHandler, run_oauth_flow


def test_oauth_flow_exchanges_callback_code_after_server_callback():
    class FakeServer:
        bound_address = None

        def __init__(self, address, handler):
            type(self).bound_address = address
            self.handler = handler
            self.timeout = None

        def handle_request(self):
            self.handler.auth_code = "auth_code"
            self.handler.received_state = "oauth_state"

        def server_close(self):
            pass

    with (
        patch("src.auth_server.HTTPServer", FakeServer),
        patch("src.auth_server.generate_code_verifier", return_value="verifier"),
        patch("src.auth_server.generate_code_challenge", return_value="challenge"),
        patch("src.auth_server.secrets.token_urlsafe", return_value="oauth_state"),
        patch("src.auth_server.build_auth_url", return_value="auth_url"),
        patch("src.auth_server.webbrowser.open") as browser_open,
        patch(
            "src.auth_server.exchange_code_for_token",
            return_value={"access_token": "token"},
        ) as exchange_code,
    ):
        result = run_oauth_flow("client_id")

    assert FakeServer.bound_address == ("127.0.0.1", CALLBACK_PORT)
    browser_open.assert_called_once_with("auth_url")
    exchange_code.assert_called_once_with("auth_code", "verifier", "client_id")
    assert result == {"access_token": "token"}
    assert _CallbackHandler.auth_code == "auth_code"
