# Spotify Widget Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first Inno Setup installer for the existing PyInstaller one-folder build.

**Architecture:** Keep packaging split in three files. `installer/SpotifyLyricsWidget.iss` describes the Windows installer, `scripts/build_installer.ps1` validates the existing PyInstaller output and runs Inno Setup, and `tests/test_installer.py` guards the installer contract with text-level checks.

**Tech Stack:** Python 3.12, pytest, PowerShell, PyInstaller one-folder output, Inno Setup 6.

---

## File Structure

- Create: `tests/test_installer.py`
  - Verifies the installer script has app metadata, file copy rules, Start Menu shortcut, optional Desktop shortcut, post-install launch, and no startup/taskbar pin behavior.
  - Verifies the build script checks for `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`, finds `ISCC.exe`, and does not rebuild/delete portable artifacts.
- Create: `installer/SpotifyLyricsWidget.iss`
  - Builds a per-user installer from `dist/SpotifyLyricsWidget`.
  - Creates Start Menu shortcut by default and optional Desktop shortcut.
  - Registers normal uninstaller metadata and uses `assets/app-icon.ico`.
- Create: `scripts/build_installer.ps1`
  - Fails clearly when PyInstaller output or Inno Setup compiler is missing.
  - Calls Inno Setup only; it does not delete, clean, zip, or run PyInstaller.

## Task 1: Installer Contract Tests

**Files:**
- Create: `tests/test_installer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_installer.py`:

```python
from pathlib import Path


ISS_PATH = Path("installer/SpotifyLyricsWidget.iss")
BUILD_SCRIPT_PATH = Path("scripts/build_installer.ps1")


def test_inno_setup_script_has_expected_setup_metadata():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert '#define MyAppName "Spotify Lyrics Widget"' in script
    assert '#define MyAppExeName "SpotifyLyricsWidget.exe"' in script
    assert '#define MyAppVersion "3.0.0"' in script
    assert "AppId={{" in script
    assert "AppName={#MyAppName}" in script
    assert "AppVersion={#MyAppVersion}" in script
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in script
    assert "PrivilegesRequired=lowest" in script
    assert "SetupIconFile=..\\assets\\app-icon.ico" in script
    assert "UninstallDisplayName={#MyAppName}" in script
    assert "UninstallDisplayIcon={app}\\{#MyAppExeName}" in script


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


def test_inno_setup_script_can_launch_app_after_install():
    script = ISS_PATH.read_text(encoding="utf-8")

    assert "[Run]" in script
    assert 'Filename: "{app}\\{#MyAppExeName}"' in script
    assert "postinstall" in script
    assert "skipifsilent" in script


def test_inno_setup_script_does_not_create_startup_or_taskbar_pin_entries():
    script = ISS_PATH.read_text(encoding="utf-8").lower()

    assert "startup" not in script
    assert "taskbar" not in script
    assert "pintotaskbar" not in script
    assert "quicklaunch" not in script


def test_build_installer_script_validates_inputs_and_finds_iscc():
    script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "$sourceExe = Join-Path $projectRoot \"dist\\SpotifyLyricsWidget\\SpotifyLyricsWidget.exe\"" in script
    assert "Build output not found" in script
    assert "Get-Command ISCC.exe" in script
    assert "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" in script
    assert "C:\\Program Files\\Inno Setup 6\\ISCC.exe" in script
    assert "Inno Setup compiler not found" in script
    assert "& $isccPath $scriptPath" in script


def test_build_installer_script_only_builds_installer():
    script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "python -m PyInstaller" not in script
    assert "Compress-Archive" not in script
    assert "Remove-Item" not in script
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_installer.py -q
```

Expected: FAIL with `FileNotFoundError` for `installer/SpotifyLyricsWidget.iss`.

- [ ] **Step 3: Commit tests**

Skip a standalone commit here; commit Task 1 with Task 2 once the installer script exists.

## Task 2: Inno Setup Script

**Files:**
- Create: `installer/SpotifyLyricsWidget.iss`
- Modify: `tests/test_installer.py`

- [ ] **Step 1: Add Inno Setup script**

Create `installer/SpotifyLyricsWidget.iss`:

```ini
#define MyAppName "Spotify Lyrics Widget"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Spotify Lyrics Widget"
#define MyAppExeName "SpotifyLyricsWidget.exe"

[Setup]
AppId={{C9A481B4-A950-4B2A-8B41-7C297C3D6F64}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SpotifyLyricsWidgetSetup
SetupIconFile=..\assets\app-icon.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\SpotifyLyricsWidget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\app-icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\app-icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
```

- [ ] **Step 2: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_installer.py -q
```

Expected: FAIL only for missing `scripts/build_installer.ps1`.

## Task 3: Installer Build Script

**Files:**
- Create: `scripts/build_installer.ps1`

- [ ] **Step 1: Add build script**

Create `scripts/build_installer.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$sourceExe = Join-Path $projectRoot "dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe"
if (!(Test-Path -LiteralPath $sourceExe)) {
    throw "Build output not found: $sourceExe. Run scripts\build_portable.ps1 first."
}

$scriptPath = Join-Path $projectRoot "installer\SpotifyLyricsWidget.iss"
if (!(Test-Path -LiteralPath $scriptPath)) {
    throw "Installer script not found: $scriptPath"
}

$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$defaultCompilerPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
if ($isccCommand) {
    $isccPath = $isccCommand.Source
} else {
    foreach ($candidate in $defaultCompilerPaths) {
        if (Test-Path -LiteralPath $candidate) {
            $isccPath = $candidate
            break
        }
    }
}

if (!$isccPath) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH."
}

& $isccPath $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

Write-Host "Installer build completed:"
Write-Host (Join-Path $projectRoot "dist\SpotifyLyricsWidgetSetup.exe")
```

- [ ] **Step 2: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_installer.py -q
```

Expected: `7 passed`.

- [ ] **Step 3: Commit installer files**

Run:

```powershell
git status --short
git add tests/test_installer.py installer/SpotifyLyricsWidget.iss scripts/build_installer.ps1 docs/superpowers/plans/2026-06-24-spotify-widget-installer.md
git commit -m "build: add Inno Setup installer"
```

## Task 4: Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Run full tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Check build script environment**

Run:

```powershell
Get-Command ISCC.exe -ErrorAction SilentlyContinue
```

Expected on this machine before installing Inno Setup: no output.

- [ ] **Step 3: If Inno Setup is available, build installer**

Run only when `ISCC.exe` exists:

```powershell
scripts\build_installer.ps1
```

Expected: `dist/SpotifyLyricsWidgetSetup.exe`.

## Self-Review

- Spec coverage: Start Menu shortcut, optional Desktop shortcut, uninstaller metadata, app icon, install current PyInstaller folder, launch after install, no startup-on-boot, and no taskbar pin are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Scope check: MSIX, code signing, Microsoft Store, startup-on-boot, and taskbar pinning remain out of scope.
- Type consistency: file paths and names match the existing `SpotifyLyricsWidget.spec` output.
