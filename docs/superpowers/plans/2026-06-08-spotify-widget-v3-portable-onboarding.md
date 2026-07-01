# Spotify Widget V3 Portable Onboarding Implementation Plan

> 狀態：歷史 plan。V3 portable onboarding 已被 V3.2 installer-only release 取代；目前產品發布頁不得再把 portable zip 當正式發布格式。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做出 V3 portable onboarding：使用者下載 portable zip、執行 `SpotifyLyricsWidget.exe`，第一次啟動時由設定視窗引導取得自己的 Spotify Client ID。

**Architecture:** 新增 `src/onboarding.py` 負責 first-run 設定視窗，`src/main.py` 只在缺少 `client_id` 時呼叫它。打包採 PyInstaller one-folder，release zip 附 `README.md`，config/log 仍保留在 `%APPDATA%/spotify-lyrics-widget/`。

**Tech Stack:** Python 3.12、PyQt6、pytest、pytest-qt、PyInstaller、PowerShell。

---

## Scope

本計畫只做 V3 的第一個公開使用門檻：

- first-run Spotify 設定視窗。
- 免 Python 的 PyInstaller one-folder portable build。
- release zip 備用中文 README。
- 測試與 build script。

本計畫不做 installer、單一 exe、code signing、完整 data-portable mode、Spotify extended quota。

## File Structure

- Create: `src/onboarding.py`
  - 負責 PyQt first-run 設定視窗。
  - 提供 Dashboard 開啟、Redirect URI 複製、Client ID 輸入與非空檢查。
- Modify: `src/main.py`
  - 缺少 `client_id` 時改用 `SpotifyOnboardingDialog`。
  - 既有 OAuth flow、worker flow、tray flow 不改。
- Create: `tests/test_onboarding.py`
  - 測 onboarding dialog 的文字、按鈕、剪貼簿、Dashboard URL、Client ID 接受邏輯。
- Modify: `tests/test_main.py`
  - 測 app startup 是否正確接 onboarding。
- Create: `README.md`
  - 給 release zip 使用者看的短版中文教學。
- Create: `tests/test_readme.py`
  - 確認 README 有 exe、Redirect URI、Client ID、log path。
- Create: `SpotifyLyricsWidget.spec`
  - PyInstaller one-folder build 設定。
- Create: `scripts/build_portable.ps1`
  - 建立 one-folder build、複製 README、壓成 zip。
- Modify: `.gitignore`
  - 保留 `dist/`、`build/` 忽略，但允許 commit `SpotifyLyricsWidget.spec`。
- Modify: `requirements.txt`
  - 加入 `pyinstaller>=6.0.0`。
- Create: `tests/test_packaging.py`
  - 確認 spec、build script、gitignore、requirements 都符合 release 需求。

---

### Task 1: First-Run Onboarding Dialog

**Files:**
- Create: `src/onboarding.py`
- Create: `tests/test_onboarding.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_onboarding.py`:

```python
from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

from src.auth import REDIRECT_URI
from src.onboarding import DASHBOARD_URL, SpotifyOnboardingDialog


def _label_texts(dialog):
    return [label.text() for label in dialog.findChildren(QLabel)]


def test_dialog_displays_redirect_uri(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    assert any(REDIRECT_URI in text for text in _label_texts(dialog))


def test_copy_redirect_uri_puts_value_on_clipboard(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    button = dialog.findChild(QPushButton, "copy_redirect_uri_button")
    button.click()

    assert QApplication.clipboard().text() == REDIRECT_URI


def test_open_dashboard_uses_spotify_dashboard_url(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    button = dialog.findChild(QPushButton, "open_dashboard_button")

    with patch("src.onboarding.QDesktopServices.openUrl") as open_url:
        button.click()

    open_url.assert_called_once()
    assert open_url.call_args.args[0].toString() == DASHBOARD_URL


def test_accept_strips_client_id(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)
    input_box = dialog.findChild(QLineEdit, "client_id_input")
    input_box.setText("  client-123  ")

    buttons = dialog.findChild(QDialogButtonBox, "dialog_buttons")
    buttons.button(QDialogButtonBox.StandardButton.Ok).click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.client_id == "client-123"


def test_empty_client_id_warns_and_stays_open(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)
    input_box = dialog.findChild(QLineEdit, "client_id_input")
    input_box.setText("   ")

    buttons = dialog.findChild(QDialogButtonBox, "dialog_buttons")

    with patch("src.onboarding.QMessageBox.warning") as warning:
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()

    warning.assert_called_once()
    assert dialog.result() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_onboarding.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.onboarding'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/onboarding.py`:

```python
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DASHBOARD_URL = "https://developer.spotify.com/dashboard"


class SpotifyOnboardingDialog(QDialog):
    def __init__(self, redirect_uri: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._redirect_uri = redirect_uri
        self._client_id = ""

        self.setWindowTitle("Spotify 初始設定")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "第一次使用前，需要建立一個 Spotify Developer App，"
            "然後把 Client ID 貼回這裡。"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        dashboard_row = QHBoxLayout()
        dashboard_text = QLabel("1. 開啟 Spotify Developer Dashboard")
        dashboard_button = QPushButton("開啟 Dashboard")
        dashboard_button.setObjectName("open_dashboard_button")
        dashboard_button.clicked.connect(self._open_dashboard)
        dashboard_row.addWidget(dashboard_text, 1)
        dashboard_row.addWidget(dashboard_button)
        layout.addLayout(dashboard_row)

        redirect_label = QLabel("2. 把這個 Redirect URI 加到你的 Spotify app")
        layout.addWidget(redirect_label)

        redirect_row = QHBoxLayout()
        redirect_value = QLabel(self._redirect_uri)
        redirect_value.setObjectName("redirect_uri_label")
        redirect_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_button = QPushButton("複製 Redirect URI")
        copy_button.setObjectName("copy_redirect_uri_button")
        copy_button.clicked.connect(self._copy_redirect_uri)
        redirect_row.addWidget(redirect_value, 1)
        redirect_row.addWidget(copy_button)
        layout.addLayout(redirect_row)

        client_label = QLabel("3. 貼上你的 Client ID")
        layout.addWidget(client_label)

        self._client_id_input = QLineEdit()
        self._client_id_input.setObjectName("client_id_input")
        self._client_id_input.setPlaceholderText("Spotify App Client ID")
        layout.addWidget(self._client_id_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.setObjectName("dialog_buttons")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("連接 Spotify")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def client_id(self) -> str:
        return self._client_id

    def _open_dashboard(self):
        QDesktopServices.openUrl(QUrl(DASHBOARD_URL))

    def _copy_redirect_uri(self):
        QApplication.clipboard().setText(self._redirect_uri)

    def _try_accept(self):
        client_id = self._client_id_input.text().strip()
        if not client_id:
            QMessageBox.warning(self, "Client ID required", "請貼上 Spotify App Client ID。")
            return
        self._client_id = client_id
        self.accept()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_onboarding.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/onboarding.py tests/test_onboarding.py
git commit -m "feat: add Spotify onboarding dialog"
```

---

### Task 2: Wire Onboarding Into Startup

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Modify the import block at the top of `tests/test_main.py`:

```python
import logging
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog

import src.main as main_module
from src.main import App
from src.spotify_worker import PlayerState
```

Add these tests after `_make_app()`:

```python
def test_start_missing_client_id_uses_onboarding_dialog():
    app, config, _ = _make_app()
    config.client_id = None
    config.size_preset = "large"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.client_id = "client-from-dialog"

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog) as dialog_class,
        patch("src.main.TrayIcon"),
    ):
        app.start()

    dialog_class.assert_called_once_with(main_module.REDIRECT_URI)
    assert config.client_id == "client-from-dialog"
    config.save.assert_called_once()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()


def test_start_cancelled_onboarding_exits_without_starting_workers():
    app, config, _ = _make_app()
    config.client_id = None
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected

    with (
        patch("src.main.SpotifyOnboardingDialog", return_value=dialog),
        patch("src.main.sys.exit", side_effect=SystemExit) as exit_app,
        pytest.raises(SystemExit),
    ):
        app.start()

    exit_app.assert_called_once_with(1)
    config.save.assert_not_called()
    app._spotify_worker.start.assert_not_called()


def test_start_existing_client_id_skips_onboarding_dialog():
    app, config, _ = _make_app()
    config.client_id = "existing-client"
    config.size_preset = "large"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.SpotifyOnboardingDialog") as dialog_class,
        patch("src.main.TrayIcon"),
    ):
        app.start()

    dialog_class.assert_not_called()
    app._ensure_auth.assert_called_once()
    app._spotify_worker.start.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_main.py::test_start_missing_client_id_uses_onboarding_dialog tests/test_main.py::test_start_cancelled_onboarding_exits_without_starting_workers tests/test_main.py::test_start_existing_client_id_skips_onboarding_dialog -q
```

Expected: FAIL because `src.main` has no `SpotifyOnboardingDialog` and still uses `QInputDialog`.

- [ ] **Step 3: Write minimal implementation**

Modify the imports in `src/main.py`:

```python
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from src.auth import (
    REDIRECT_URI,
    SCOPES,
    has_required_scopes,
    is_token_expired,
    refresh_access_token,
)
from src.onboarding import SpotifyOnboardingDialog
```

Replace the `if not self._config.client_id:` block in `App.start()` with:

```python
        if not self._config.client_id:
            dialog = SpotifyOnboardingDialog(REDIRECT_URI)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                sys.exit(1)
            self._config.client_id = dialog.client_id
            self._config.save()
```

Remove `QInputDialog` from the old imports.

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```powershell
pytest tests/test_main.py::test_start_missing_client_id_uses_onboarding_dialog tests/test_main.py::test_start_cancelled_onboarding_exits_without_starting_workers tests/test_main.py::test_start_existing_client_id_skips_onboarding_dialog -q
```

Expected: `3 passed`.

- [ ] **Step 5: Run main startup regression tests**

Run:

```powershell
pytest tests/test_main.py -q
```

Expected: all tests in `tests/test_main.py` pass.

- [ ] **Step 6: Commit**

```powershell
git add src/main.py tests/test_main.py
git commit -m "feat: show onboarding when client id is missing"
```

---

### Task 3: Release README

**Files:**
- Create: `README.md`
- Create: `tests/test_readme.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_readme.py`:

```python
from pathlib import Path


def test_readme_documents_portable_startup_and_spotify_setup():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "SpotifyLyricsWidget.exe" in text
    assert "http://127.0.0.1:8888/callback" in text
    assert "Client ID" in text
    assert "%APPDATA%/spotify-lyrics-widget" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_readme.py -q
```

Expected: FAIL because `README.md` does not exist.

- [ ] **Step 3: Write README**

Create `README.md`:

```markdown
# Spotify Lyrics Widget

Windows 桌面 Spotify 歌詞小工具。

## 使用方式

1. 下載 portable zip。
2. 解壓縮整個資料夾。
3. 執行 `SpotifyLyricsWidget.exe`。
4. 第一次啟動時，依照「Spotify 初始設定」視窗完成 Spotify 設定。

## 第一次 Spotify 設定

這個工具需要你自己的 Spotify App Client ID。

1. 在設定視窗按「開啟 Dashboard」。
2. 到 Spotify Developer Dashboard 建立一個 app。
3. 在 Spotify app 設定裡加入 Redirect URI：

```text
http://127.0.0.1:8888/callback
```

4. 複製 Spotify app 的 Client ID。
5. 回到工具，把 Client ID 貼上。
6. 按「連接 Spotify」，瀏覽器會開啟 Spotify 登入授權。

## 資料位置

設定和 log 會放在：

```text
%APPDATA%/spotify-lyrics-widget
```

更新新版時，可以替換 app 資料夾；原本的 token 和設定會保留。

## 常見問題

如果 Spotify 顯示 invalid redirect URI，請確認 Spotify Dashboard 裡的 Redirect URI 完全等於：

```text
http://127.0.0.1:8888/callback
```

如果 app 沒有反應，可以查看 log：

```text
%APPDATA%/spotify-lyrics-widget/widget.log
```
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_readme.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add README.md tests/test_readme.py
git commit -m "docs: add portable setup readme"
```

---

### Task 4: PyInstaller Portable Packaging

**Files:**
- Create: `SpotifyLyricsWidget.spec`
- Create: `scripts/build_portable.ps1`
- Create: `tests/test_packaging.py`
- Modify: `.gitignore`
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_packaging.py`:

```python
from pathlib import Path


def test_pyinstaller_spec_keeps_windowed_app_and_font_asset():
    spec = Path("SpotifyLyricsWidget.spec").read_text(encoding="utf-8")

    assert "console=False" in spec
    assert "assets/fonts/NotoSansTC-VF.ttf" in spec
    assert 'name="SpotifyLyricsWidget"' in spec


def test_build_script_creates_portable_release_without_deleting_outputs():
    script = Path("scripts/build_portable.ps1").read_text(encoding="utf-8")

    assert "python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec" in script
    assert "Copy-Item -LiteralPath \"README.md\"" in script
    assert "Compress-Archive" in script
    assert "Remove-Item" not in script


def test_gitignore_allows_committed_pyinstaller_spec():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "*.spec" in gitignore
    assert "!SpotifyLyricsWidget.spec" in gitignore


def test_pyinstaller_is_listed_for_release_builds():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()

    assert "pyinstaller" in requirements
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_packaging.py -q
```

Expected: FAIL because `SpotifyLyricsWidget.spec` and `scripts/build_portable.ps1` do not exist, `.gitignore` still ignores all `*.spec`, and `requirements.txt` has no PyInstaller.

- [ ] **Step 3: Add PyInstaller to requirements**

Modify `requirements.txt` so it contains:

```text
PyQt6>=6.6.0
httpx>=0.27.0
pytest>=8.0.0
pytest-qt>=4.4.0
zhconv>=1.4.3
pyinstaller>=6.0.0
```

- [ ] **Step 4: Allow the project spec file in git**

Modify `.gitignore` so the spec section becomes:

```text
dist/
build/
*.spec
!SpotifyLyricsWidget.spec
```

- [ ] **Step 5: Create PyInstaller spec**

Create `SpotifyLyricsWidget.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["run.pyw"],
    pathex=[],
    binaries=[],
    datas=[("assets/fonts/NotoSansTC-VF.ttf", "assets/fonts")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpotifyLyricsWidget",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SpotifyLyricsWidget",
)
```

- [ ] **Step 6: Create portable build script**

Create `scripts/build_portable.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec

$sourceDir = Join-Path $projectRoot "dist\SpotifyLyricsWidget"
if (!(Test-Path -LiteralPath $sourceDir)) {
    throw "Build output not found: $sourceDir"
}

$releaseDir = Join-Path $projectRoot "dist\SpotifyLyricsWidget-v3-portable"
if (Test-Path -LiteralPath $releaseDir) {
    throw "Release folder already exists: $releaseDir"
}

$zipPath = Join-Path $projectRoot "dist\SpotifyLyricsWidget-v3-portable.zip"
if (Test-Path -LiteralPath $zipPath) {
    throw "Release zip already exists: $zipPath"
}

New-Item -ItemType Directory -Path $releaseDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir "*") -Destination $releaseDir -Recurse
Copy-Item -LiteralPath "README.md" -Destination (Join-Path $releaseDir "README.md")
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath

Write-Host "Portable release created:"
Write-Host $releaseDir
Write-Host $zipPath
```

- [ ] **Step 7: Run packaging tests**

Run:

```powershell
pytest tests/test_packaging.py -q
```

Expected: `4 passed`.

- [ ] **Step 8: Commit**

```powershell
git add .gitignore requirements.txt SpotifyLyricsWidget.spec scripts/build_portable.ps1 tests/test_packaging.py
git commit -m "build: add portable PyInstaller packaging"
```

---

### Task 5: Verification And Build Smoke Test

**Files:**
- No new source files.
- This task verifies the combined result.

- [ ] **Step 1: Run focused onboarding tests**

Run:

```powershell
pytest tests/test_onboarding.py tests/test_main.py::test_start_missing_client_id_uses_onboarding_dialog tests/test_main.py::test_start_cancelled_onboarding_exits_without_starting_workers tests/test_main.py::test_start_existing_client_id_skips_onboarding -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run docs and packaging tests**

Run:

```powershell
pytest tests/test_readme.py tests/test_packaging.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
pytest -q
```

Expected: full suite passes with no failures.

- [ ] **Step 4: Build portable folder**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_portable.ps1
```

Expected output includes:

```text
Portable release created:
```

Expected files:

```text
dist/SpotifyLyricsWidget-v3-portable/SpotifyLyricsWidget.exe
dist/SpotifyLyricsWidget-v3-portable/README.md
dist/SpotifyLyricsWidget-v3-portable.zip
```

- [ ] **Step 5: Manual first-run smoke test**

Use a clean config directory before this test by temporarily renaming `%APPDATA%/spotify-lyrics-widget` outside the app, then restore it after the smoke test.

Manual checks:

```text
1. Run dist/SpotifyLyricsWidget-v3-portable/SpotifyLyricsWidget.exe
2. Confirm Spotify 初始設定 appears.
3. Click 開啟 Dashboard and confirm browser opens https://developer.spotify.com/dashboard.
4. Click 複製 Redirect URI and confirm clipboard contains http://127.0.0.1:8888/callback.
5. Paste a valid Client ID and click 連接 Spotify.
6. Complete OAuth.
7. Confirm widget appears, tray appears, size menu works, and Quit closes the app.
8. Confirm log exists at %APPDATA%/spotify-lyrics-widget/widget.log.
```

- [ ] **Step 6: Commit verification notes if a release doc is updated**

If verification adds a handoff or changelog entry, commit only that doc:

```powershell
git add docs/superpowers/plans/2026-06-08-spotify-widget-v3-portable-onboarding.md
git commit -m "docs: record V3 portable verification"
```

Skip this commit if no release/handoff doc changed.

---

## Self-Review

Spec coverage:

- first-run setup dialog: Task 1 and Task 2.
- user-owned Spotify Client ID: Task 1, Task 2, README in Task 3.
- Dashboard button: Task 1.
- Copy Redirect URI: Task 1.
- existing OAuth flow preserved: Task 2 only changes missing-client-id branch.
- `%APPDATA%` config persistence: Task 3 documents it; implementation keeps `src/config.py` unchanged.
- PyInstaller one-folder build: Task 4.
- release zip with README: Task 4.
- generated `dist/` and zip out of git: Task 4 keeps ignored artifacts.
- manual smoke test: Task 5.

Placeholder scan:

- 沒有待補標記。
- No unspecified helper functions.
- Every code-changing task includes exact file paths, code blocks, commands, expected result, and commit command.

Type consistency:

- `SpotifyOnboardingDialog.client_id` is a string property used by `src/main.py`.
- `DASHBOARD_URL` is a module constant tested through `QDesktopServices.openUrl`.
- `REDIRECT_URI` remains sourced from `src.auth`.
