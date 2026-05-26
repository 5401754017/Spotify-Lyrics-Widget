from pathlib import Path

from src import shortcuts


def test_pythonw_path_derives_from_python_exe():
    python = Path(r"C:\Python312\python.exe")
    assert shortcuts.pythonw_path(python) == Path(r"C:\Python312\pythonw.exe")


def test_shortcut_locations():
    home = Path(r"C:\Users\me")
    appdata = Path(r"C:\Users\me\AppData\Roaming")

    locations = shortcuts.shortcut_locations(home=home, appdata=appdata)

    assert locations.desktop == home / "Desktop" / "Spotify Lyrics Widget.lnk"
    assert locations.start_menu == (
        appdata
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Spotify Lyrics Widget.lnk"
    )


def test_build_powershell_script_escapes_paths():
    script = shortcuts.build_powershell_script(
        pythonw=Path(r"C:\Python312\pythonw.exe"),
        run_script=Path(r"C:\Project's Folder\run.pyw"),
        working_dir=Path(r"C:\Project's Folder"),
        locations=shortcuts.ShortcutLocations(
            desktop=Path(r"C:\Users\me\Desktop\Spotify Lyrics Widget.lnk"),
            start_menu=Path(
                r"C:\Users\me\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Spotify Lyrics Widget.lnk"
            ),
        ),
    )

    assert "WScript.Shell" in script
    assert "CreateShortcut" in script
    assert "C:\\Python312\\pythonw.exe" in script
    assert "Project''s Folder" in script
    assert "\"C:\\Project''s Folder\\run.pyw\"" in script


def test_create_shortcuts_invokes_powershell(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr(shortcuts.subprocess, "run", fake_run)

    locations = shortcuts.create_shortcuts(
        project_root=tmp_path,
        python_executable=Path(r"C:\Python312\python.exe"),
        home=tmp_path / "home",
        appdata=tmp_path / "appdata",
    )

    assert locations.desktop.name == "Spotify Lyrics Widget.lnk"
    assert calls
    command, check = calls[0]
    assert check is True
    assert command[:3] == ["powershell", "-NoProfile", "-ExecutionPolicy"]
