from pathlib import Path


def test_pyinstaller_spec_keeps_windowed_app_and_font_asset():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert "console=False" in spec
    assert "assets/fonts/NotoSansTC-VF.ttf" in spec
    assert 'name="SpotifyLyricsWidget"' in spec


def test_build_script_creates_portable_release_without_deleting_outputs():
    script = Path("scripts/build_portable.ps1").read_text(encoding="utf-8")

    assert "python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec" in script
    assert 'Copy-Item -LiteralPath "README.md"' in script
    assert "Compress-Archive" in script
    assert "Remove-Item" not in script


def test_gitignore_allows_committed_pyinstaller_spec():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "*.spec" in gitignore
    assert "!SpotifyLyricsWidget.spec" in gitignore


def test_pyinstaller_is_listed_for_release_builds():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()

    assert "pyinstaller" in requirements
