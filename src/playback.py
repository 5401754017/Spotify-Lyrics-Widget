import logging
import time
from collections.abc import Callable
from urllib.parse import urlencode

import httpx
from PyQt6.QtCore import QRunnable, QThreadPool


PLAY_URL = "https://api.spotify.com/v1/me/player/play"
PAUSE_URL = "https://api.spotify.com/v1/me/player/pause"
NEXT_URL = "https://api.spotify.com/v1/me/player/next"
PREVIOUS_URL = "https://api.spotify.com/v1/me/player/previous"
DEVICES_URL = "https://api.spotify.com/v1/me/player/devices"
BODY_SNIPPET_LIMIT = 150
DEFAULT_RETRY_AFTER_SECONDS = 1


def build_control_request(action: str, is_playing: bool) -> tuple[str, str]:
    if action == "toggle":
        return ("PUT", PAUSE_URL if is_playing else PLAY_URL)
    if action == "next":
        return ("POST", NEXT_URL)
    if action == "previous":
        return ("POST", PREVIOUS_URL)
    raise ValueError(f"Unknown playback action: {action}")


class _ControlTask(QRunnable):
    def __init__(
        self,
        method: str,
        url: str,
        access_token: str,
        on_done: Callable[[], None],
        on_rate_limited: Callable[[int], None],
    ):
        super().__init__()
        self.method = method
        self.url = url
        self.access_token = access_token
        self.on_done = on_done
        self.on_rate_limited = on_rate_limited

    def run(self):
        try:
            response = _request(self.method, self.url, self.access_token)
            if self._handle_rate_limit(response):
                return
            if _should_retry_play_with_device(self.method, self.url, response):
                self._retry_play_with_available_device()
                return
            _log_control_failure(self.method, self.url, response)
        except Exception as error:
            logging.warning(
                "Playback control request failed: %s %s: %s: %s",
                self.method,
                self.url,
                type(error).__name__,
                error,
            )
        finally:
            self.on_done()

    def _retry_play_with_available_device(self):
        response = _request("GET", DEVICES_URL, self.access_token)
        if self._handle_rate_limit(response):
            return
        if response.status_code >= 300:
            _log_control_failure("GET", DEVICES_URL, response)
            return

        device_id = _select_playback_device_id(response.json().get("devices", []))
        if not device_id:
            logging.warning("No available Spotify device for playback resume")
            return

        retry_url = _play_url(device_id)
        retry_response = _request("PUT", retry_url, self.access_token)
        if self._handle_rate_limit(retry_response):
            return
        _log_control_failure("PUT", retry_url, retry_response)

    def _handle_rate_limit(self, response) -> bool:
        if response.status_code != 429:
            return False
        retry_after = _parse_retry_after(response)
        self.on_rate_limited(retry_after)
        logging.warning(
            "Playback control rate limited: retry after %s seconds",
            retry_after,
        )
        return True


def _request(method: str, url: str, access_token: str):
    return httpx.request(
        method,
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=5.0,
    )


def _parse_retry_after(response) -> int:
    try:
        return max(
            1,
            int(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS)),
        )
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_SECONDS


def _body_snippet(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= BODY_SNIPPET_LIMIT:
        return text
    return f"{text[:BODY_SNIPPET_LIMIT]}..."


def _log_control_failure(method: str, url: str, response):
    if response.status_code < 300:
        return
    logging.warning(
        "Playback control failed: %s %s -> %s %s",
        method,
        url,
        response.status_code,
        _body_snippet(response.text),
    )


def _should_retry_play_with_device(method: str, url: str, response) -> bool:
    return (
        method == "PUT"
        and url == PLAY_URL
        and response.status_code == 404
        and "active device" in (response.text or "").lower()
    )


def _select_playback_device_id(devices: list[dict]) -> str | None:
    eligible = [
        device
        for device in devices
        if device.get("id") and not device.get("is_restricted", False)
    ]
    if not eligible:
        return None
    active = next((device for device in eligible if device.get("is_active")), None)
    return (active or eligible[0])["id"]


def _play_url(device_id: str) -> str:
    return f"{PLAY_URL}?{urlencode({'device_id': device_id})}"


class PlaybackController:
    def __init__(self, config, pool=None):
        self._config = config
        self._pool = pool or QThreadPool.globalInstance()
        self._in_flight = False
        self._cooldown_until = 0.0

    def toggle(self, is_playing: bool):
        self._dispatch("toggle", is_playing)

    def next(self):
        self._dispatch("next", True)

    def previous(self):
        self._dispatch("previous", True)

    def _dispatch(self, action: str, is_playing: bool):
        if self._in_flight or time.monotonic() < self._cooldown_until:
            return
        method, url = build_control_request(action, is_playing)
        self._in_flight = True
        self._pool.start(
            _ControlTask(
                method,
                url,
                self._config.access_token,
                on_done=self._mark_done,
                on_rate_limited=self._set_cooldown,
            )
        )

    def _mark_done(self):
        self._in_flight = False

    def _set_cooldown(self, retry_after_seconds: int):
        self._cooldown_until = time.monotonic() + retry_after_seconds
