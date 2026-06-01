from unittest.mock import MagicMock, patch

import httpx


def test_build_control_request_maps_actions():
    from src.playback import build_control_request

    assert build_control_request("toggle", is_playing=True) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/pause",
    )
    assert build_control_request("toggle", is_playing=False) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/play",
    )
    assert build_control_request("next", is_playing=True) == (
        "POST",
        "https://api.spotify.com/v1/me/player/next",
    )
    assert build_control_request("previous", is_playing=True) == (
        "POST",
        "https://api.spotify.com/v1/me/player/previous",
    )


def test_controller_drops_duplicate_while_in_flight():
    from src.playback import PlaybackController

    pool = MagicMock()
    config = MagicMock(access_token="token")
    controller = PlaybackController(config, pool=pool)

    controller.toggle(is_playing=False)
    controller.toggle(is_playing=False)

    assert pool.start.call_count == 1


def test_controller_skips_dispatch_during_cooldown():
    from src.playback import PlaybackController

    pool = MagicMock()
    config = MagicMock(access_token="token")
    controller = PlaybackController(config, pool=pool)

    with patch("src.playback.time.monotonic", return_value=10.0):
        controller._cooldown_until = 20.0
        controller.next()

    pool.start.assert_not_called()


@patch("src.playback.httpx.request")
def test_task_logs_non_2xx_with_capped_body(mock_request, caplog):
    from src.playback import _ControlTask

    mock_request.return_value = MagicMock(status_code=403, text="x" * 400, headers={})
    on_done = MagicMock()
    task = _ControlTask(
        method="PUT",
        url="https://api.spotify.com/v1/me/player/play",
        access_token="token",
        on_done=on_done,
        on_rate_limited=MagicMock(),
    )

    task.run()

    assert any(
        "Playback control failed" in r.message and "403" in r.message
        for r in caplog.records
    )
    assert any(
        len(r.message) < 260
        for r in caplog.records
        if "Playback control failed" in r.message
    )
    on_done.assert_called_once()


@patch("src.playback.httpx.request")
def test_task_respects_retry_after_on_429(mock_request):
    from src.playback import _ControlTask

    mock_request.return_value = MagicMock(
        status_code=429,
        text="rate limited",
        headers={"Retry-After": "5"},
    )
    on_rate_limited = MagicMock()
    task = _ControlTask(
        method="POST",
        url="https://api.spotify.com/v1/me/player/next",
        access_token="token",
        on_done=MagicMock(),
        on_rate_limited=on_rate_limited,
    )

    task.run()

    on_rate_limited.assert_called_once_with(5)


@patch("src.playback.httpx.request")
def test_task_logs_request_exception(mock_request, caplog):
    from src.playback import _ControlTask

    mock_request.side_effect = httpx.ConnectError("offline")
    task = _ControlTask(
        method="POST",
        url="https://api.spotify.com/v1/me/player/next",
        access_token="token",
        on_done=MagicMock(),
        on_rate_limited=MagicMock(),
    )

    task.run()

    assert any(
        "Playback control request failed" in r.message and "ConnectError" in r.message
        for r in caplog.records
    )
