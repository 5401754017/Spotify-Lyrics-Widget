from pathlib import Path


def test_readme_documents_portable_startup_and_spotify_setup():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "SpotifyLyricsWidget.exe" in text
    assert "http://127.0.0.1:8888/callback" in text
    assert "Client ID" in text
    assert "%APPDATA%/spotify-lyrics-widget" in text
