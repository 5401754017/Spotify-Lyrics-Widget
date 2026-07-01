from pathlib import Path


ISS_PATH = Path("installer/SpotifyLyricsWidget.iss")
BUILD_SCRIPT_PATH = Path("scripts/build_installer.ps1")


def test_inno_setup_script_has_expected_setup_metadata():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert '#define MyAppName "Spotify Lyrics Widget"' in script
    assert '#define MyAppExeName "SpotifyLyricsWidget.exe"' in script
    assert '#define MyAppVersion "3.2.0"' in script
    assert "AppId={{" in script
    assert "AppName={#MyAppName}" in script
    assert "AppVersion={#MyAppVersion}" in script
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in script
    assert "PrivilegesRequired=lowest" in script
    assert "SetupIconFile=..\\assets\\app-icon.ico" in script
    assert "UninstallDisplayName={#MyAppName}" in script
    assert "UninstallDisplayIcon={app}\\{#MyAppExeName}" in script


def test_inno_setup_script_offers_first_run_language_page():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "[Code]" in script
    assert "CreateInputOptionPage" in script
    assert "'Language / 語言'" in script
    assert "LanguagePage.Add('English')" in script
    assert "LanguagePage.Add('繁體中文')" in script
    assert "LanguagePage.Values[0] := True" in script


def test_inno_setup_script_records_selected_language_for_first_run():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "ForceDirectories(ExpandConstant('{userappdata}\\spotify-lyrics-widget'))" in script
    assert "SetIniString(" in script
    assert "'Install'" in script
    assert "'Language'" in script
    assert "SelectedAppLanguage" in script
    assert "ExpandConstant('{userappdata}\\spotify-lyrics-widget\\install.ini')" in script


def test_inno_setup_script_installs_pyinstaller_folder():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "[Files]" in script
    assert 'Source: "..\\dist\\SpotifyLyricsWidget\\*"' in script
    assert 'DestDir: "{app}"' in script
    assert "recursesubdirs" in script
    assert "createallsubdirs" in script


def test_inno_setup_script_creates_start_menu_and_optional_desktop_shortcuts():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "[Tasks]" in script
    assert 'Name: "desktopicon"' in script
    assert "checkedonce" in script
    assert "[Icons]" in script
    assert 'Name: "{group}\\{#MyAppName}"' in script
    assert 'Name: "{autodesktop}\\{#MyAppName}"' in script
    assert "Tasks: desktopicon" in script


def test_inno_setup_shortcuts_use_installed_exe_icon():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert 'IconFilename: "{app}\\{#MyAppExeName}"' in script
    assert 'IconFilename: "{app}\\assets\\app-icon.ico"' not in script
    assert 'IconFilename: "{app}\\_internal\\assets\\app-icon.ico"' not in script


def test_inno_setup_script_can_launch_app_after_install():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "[Run]" in script
    assert 'Filename: "{app}\\{#MyAppExeName}"' in script
    assert "postinstall" in script
    assert "skipifsilent" in script


def test_inno_setup_script_refreshes_shell_icons_after_install():
    script = ISS_PATH.read_text(encoding="utf-8")
    ie4uinit_run_line = next(
        line for line in script.splitlines() if '"{sysnative}\\ie4uinit.exe"' in line
    )

    assert 'Filename: "{sysnative}\\ie4uinit.exe"' in ie4uinit_run_line
    assert 'Parameters: "-show"' in ie4uinit_run_line
    assert "runhidden" in ie4uinit_run_line
    assert "nowait" in ie4uinit_run_line
    assert "skipifdoesntexist" in ie4uinit_run_line


def test_inno_setup_script_does_not_create_startup_or_taskbar_pin_entries():
    script = ISS_PATH.read_text(encoding="utf-8").lower()

    assert "startup" not in script
    assert "taskbar" not in script
    assert "pintotaskbar" not in script
    assert "quicklaunch" not in script


def test_build_installer_script_validates_inputs_and_finds_iscc():
    script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    assert (
        "$sourceExe = Join-Path $projectRoot "
        '"dist\\SpotifyLyricsWidget\\SpotifyLyricsWidget.exe"'
    ) in script
    assert "Run scripts\\build_app.ps1 first" in script
    assert "Get-Command ISCC.exe" in script
    assert "$env:LOCALAPPDATA" in script
    assert "Programs\\Inno Setup 6\\ISCC.exe" in script
    assert "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" in script
    assert "C:\\Program Files\\Inno Setup 6\\ISCC.exe" in script
    assert "Inno Setup compiler not found" in script
    assert "& $isccPath $scriptPath" in script


def test_build_installer_script_only_builds_installer():
    script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "python -m PyInstaller" not in script
    assert "Compress-Archive" not in script
    assert "Remove-Item" not in script
