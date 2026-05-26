import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Spotify Lyrics Widget"


@dataclass(frozen=True)
class ShortcutLocations:
    desktop: Path
    start_menu: Path


def pythonw_path(python_executable: Path | None = None) -> Path:
    executable = Path(python_executable or sys.executable)
    if executable.name.lower() == "python.exe":
        return executable.with_name("pythonw.exe")
    return executable


def shortcut_locations(
    home: Path | None = None, appdata: Path | None = None
) -> ShortcutLocations:
    user_home = Path(home or Path.home())
    roaming = Path(appdata or os.environ.get("APPDATA", user_home))
    shortcut_name = f"{APP_NAME}.lnk"
    return ShortcutLocations(
        desktop=user_home / "Desktop" / shortcut_name,
        start_menu=roaming
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / shortcut_name,
    )


def _ps_quote(path: Path | str) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _quoted_argument(path: Path) -> str:
    return f'"{path}"'


def build_powershell_script(
    pythonw: Path, run_script: Path, working_dir: Path, locations: ShortcutLocations
) -> str:
    return f"""
$shell = New-Object -ComObject WScript.Shell
$shortcuts = @(
    @{{ Path = {_ps_quote(locations.desktop)} }},
    @{{ Path = {_ps_quote(locations.start_menu)} }}
)
foreach ($item in $shortcuts) {{
    $parent = Split-Path -Parent $item.Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $shortcut = $shell.CreateShortcut($item.Path)
    $shortcut.TargetPath = {_ps_quote(pythonw)}
    $shortcut.Arguments = {_ps_quote(_quoted_argument(run_script))}
    $shortcut.WorkingDirectory = {_ps_quote(working_dir)}
    $shortcut.Description = {_ps_quote(APP_NAME)}
    $shortcut.Save()
}}
""".strip()


def create_shortcuts(
    project_root: Path | None = None,
    python_executable: Path | None = None,
    home: Path | None = None,
    appdata: Path | None = None,
) -> ShortcutLocations:
    root = Path(project_root or Path(__file__).resolve().parent.parent)
    locations = shortcut_locations(home=home, appdata=appdata)
    script = build_powershell_script(
        pythonw=pythonw_path(python_executable),
        run_script=root / "run.pyw",
        working_dir=root,
        locations=locations,
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
    )
    return locations
