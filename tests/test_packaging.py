from pathlib import Path


def test_pyinstaller_spec_keeps_windowed_app_and_font_asset():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert "console=False" in spec
    assert "assets/fonts/NotoSansTC-VF.ttf" in spec
    assert 'name="SpotifyLyricsWidget"' in spec


def test_pyinstaller_spec_collects_zhconv_data_files():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert "collect_data_files" in spec
    assert 'collect_data_files("zhconv")' in spec


def test_pyinstaller_spec_uses_app_icon_asset():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert '("assets/app-icon.ico", "assets")' in spec
    assert 'icon="assets/app-icon.ico"' in spec


def test_app_icon_asset_exists():
    assert Path("assets/app-icon.ico").is_file()


def test_build_script_creates_installer_input_without_portable_zip():
    script = Path("scripts/build_app.ps1").read_text(encoding="utf-8")

    assert "python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec" in script
    assert 'Copy-Item -LiteralPath "README.md"' not in script
    assert "Compress-Archive" not in script
    assert "portable" not in script.lower()
    assert "Remove-Item" not in script


def test_build_script_checks_pyinstaller_exit_code_before_using_source_dir():
    script = Path("scripts/build_app.ps1").read_text(encoding="utf-8")

    pyinstaller_index = script.index(
        "python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec"
    )
    exit_code_index = script.index("$LASTEXITCODE")
    source_dir_index = script.index("$sourceDir")

    assert pyinstaller_index < exit_code_index < source_dir_index


def test_pyinstaller_spec_disables_upx_compression():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert "upx=False" in spec
    assert "upx=True" not in spec


def test_gitignore_allows_committed_pyinstaller_spec():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "*.spec" in gitignore
    assert "!SpotifyLyricsWidget.spec" in gitignore


def test_pyinstaller_is_listed_for_release_builds():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()

    assert "pyinstaller" in requirements
