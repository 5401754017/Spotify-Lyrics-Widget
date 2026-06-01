import logging
import time
from collections.abc import Callable

import httpx
from PyQt6.QtCore import QRunnable, QThreadPool


PLAY_URL = "https://api.spotify.com/v1/me/player/play"
PAUSE_URL = "https://api.spotify.com/v1/me/player/pause"
NEXT_URL = "https://api.spotify.com/v1/me/player/next"
PREVIOUS_URL = "https://api.spotify.com/v1/me/player/previous"
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
            response = httpx.request(
                self.method,
                self.url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5.0,
            )
            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                self.on_rate_limited(retry_after)
                logging.warning(
                    "Playback control rate limited: %s %s; retry after %s seconds",
                    self.method,
                    self.url,
                    retry_after,
                )
            elif response.status_code >= 300:
                logging.warning(
                    "Playback control failed: %s %s -> %s %s",
                    self.method,
                    self.url,
                    response.status_code,
                    _body_snippet(response.text),
                )
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
