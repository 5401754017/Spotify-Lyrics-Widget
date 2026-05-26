# Spotify Lyrics Widget V1.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the widget easy to find and reach — bundle a CJK font so Chinese renders correctly, add a system tray icon that confirms the app is running and raises the widget when covered, install Start-menu / desktop shortcuts (no startup-on-boot), and move the offline status into the lyric lane so V2 has a clean fixed top row.

**Architecture:** Three independent reachability features plus one small UI correction. `widget.py` removes the right-top offline overlay and renders offline as central status text in the existing lyric lane. `src/fonts.py` loads a bundled Noto Sans TC at startup and exposes the family name; `widget.py` reads it (falling back to Segoe UI when not loaded, so tests are unaffected). `src/tray.py` wraps `QSystemTrayIcon` and takes plain callbacks; `App` (in `main.py`) wires those callbacks to its existing `raise_window`, a new visibility toggle, an open-log action, and quit. `src/shortcuts.py` builds `.lnk` files via the Windows-built-in `WScript.Shell` COM object driven through PowerShell, with a one-shot `scripts/install_shortcuts.py` entry point.

**Tech Stack:** Python 3, PyQt6 (`QtGui`, `QtWidgets`), pytest + pytest-qt. No new third-party dependencies (PowerShell `WScript.Shell` is built into Windows; the tray icon is drawn at runtime with `QPainter`).

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `assets/fonts/NotoSansTC-VF.ttf` | Create (download) | Bundled CJK variable font covering Regular/Bold weights |
| `assets/fonts/OFL.txt` | Create (download) | SIL Open Font License for the bundled font |
| `src/fonts.py` | Create | Load bundled font into `QFontDatabase`, expose `app_font_family()` |
| `src/widget.py` | Modify | Remove right-top offline overlay; show `offline` in the lyric lane; use `app_font_family()` instead of hardcoded `"Segoe UI"`; re-tune `LYRIC_LANE_HEIGHT` |
| `src/tray.py` | Create | `QSystemTrayIcon` wrapper: runtime-drawn icon + context menu, callback-driven |
| `src/logging_setup.py` | Modify | Extract `log_file_path()` so the tray can locate `widget.log` |
| `src/main.py` | Modify | Load font before building UI; create/wire/hide the tray icon; add `_toggle_widget` / `_open_log` |
| `src/shortcuts.py` | Create | Pure path/script builders + `create_shortcuts()` side-effecting installer |
| `scripts/install_shortcuts.py` | Create | One-shot entry point the user runs to install shortcuts |
| `tests/test_fonts.py` | Create | Font loader fallback + bundled-font smoke test |
| `tests/test_tray.py` | Create | Tray icon non-null, activation reason routing, menu actions, toggle label |
| `tests/test_shortcuts.py` | Create | Script builder, `pythonw` path derivation, shortcut locations |
| `tests/test_logging_setup.py` | Modify | Add `log_file_path()` test |
| `tests/test_main.py` | Modify | Add `_toggle_widget` / `_open_log` tests |
| `tests/test_widget.py` | Modify | Offline status uses lyric lane and does not create a top-row overlay |

**All commands run from the project root** `C:\Users\crayo\personal-system\projects\spotify_widget`. `pytest.ini` sets `pythonpath = .` and `testpaths = tests`.

---

## Task 0: Move offline status into the lyric lane

**Why:** V1.2 added a top-right `offline` overlay so the layout would not jump. V2 needs that same top-right area for fixed controls and close button. Offline is also a playback/status message, so it belongs in the same lane as `no synced lyrics`, not in the title/control row.

Target layout:

```text
0     5                        50     60          80      90 95 100
+------------------------------------------------------------------+
|     Song Name - Artist Name        [V2 controls later]      [X]   |
|                                                                  |
|                         offline                                  |
|                                                                  |
+------------------------------------------------------------------+
```

**Files:**
- Modify: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Write failing tests**

Add tests covering:
- `show_offline()` sets the lyric label text to `offline`.
- No `_offline_label` overlay child exists after widget construction.
- Showing offline does not change title geometry, lyric geometry, or widget size.
- `hide_offline()` clears the offline status only when the current lyric-lane state is offline; it must not accidentally erase a real lyric that arrived after recovery.

- [ ] **Step 2: Remove the overlay child**

In `src/widget.py`, delete the `_offline_label` creation and any geometry update code for that label. Do not leave a hidden overlay around "just in case"; V2 must inherit a clean top row.

- [ ] **Step 3: Render offline through the lyric lane**

Update the public widget methods so:
- `show_offline()` stores a lightweight status flag and sets the lyric lane text to `offline`.
- `hide_offline()` clears that flag and returns the lyric lane to the current lyric/no-lyrics/not-playing state.
- The app wiring remains the same: Spotify worker network-error signal still calls `show_offline()`, recovery still calls `hide_offline()`.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_widget.py -v
```

Expected: all widget tests pass, and there is no top-row offline overlay left.

---

## Task 1: Bundle and load Noto Sans TC

**Why:** `Segoe UI` has no CJK glyphs, so Windows substitutes an ugly fallback for Chinese titles/lyrics. Noto Sans TC (= 思源黑體, SIL OFL — free to bundle) fixes this. Loading at startup and reading the family name keeps the change in one place. Tests construct the widget without loading the font, so the family falls back to `Segoe UI` and existing font tests stay green.

**Files:**
- Create: `assets/fonts/NotoSansTC-VF.ttf`, `assets/fonts/OFL.txt`
- Create: `src/fonts.py`
- Test: `tests/test_fonts.py`
- Modify: `src/widget.py:87`, `src/widget.py:111`, `src/widget.py:27`
- Modify: `src/main.py` (call `load_app_font()` in `main()`)

- [ ] **Step 1: Download the font files**

Download the Traditional Chinese variable TTF and the license from the official Noto CJK repo:
- https://github.com/googlefonts/noto-cjk/tree/main/Sans/Variable/TTF

Use exactly these asset names in the repo: `NotoSansTC-VF.ttf`, `OFL.txt`. The single variable font covers the weight range used by the title and lyric labels.

Place them at `assets/fonts/NotoSansTC-VF.ttf`. Save the `OFL.txt` license alongside it. Confirm the files exist and are non-trivial in size:

Run: `Get-ChildItem assets\fonts\`
Expected: two files listed; the `.ttf` file is several MB.

- [ ] **Step 2: Write the failing test for the font loader**

Create `tests/test_fonts.py`:

```python
from pathlib import Path

from src import fonts


def test_app_font_family_defaults_to_fallback():
    fonts._loaded_family = None
    assert fonts.app_font_family() == "Segoe UI"


def test_load_app_font_falls_back_when_files_missing(qtbot, monkeypatch, tmp_path):
    fonts._loaded_family = None
    monkeypatch.setattr(fonts, "_FONT_DIR", tmp_path)  # empty dir, no font files
    assert fonts.load_app_font() == "Segoe UI"


def test_load_app_font_loads_bundled_noto(qtbot):
    fonts._loaded_family = None
    family = fonts.load_app_font()
    assert "Noto" in family
    assert fonts.app_font_family() == family
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/test_fonts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.fonts'`.

- [ ] **Step 4: Implement `src/fonts.py`**

```python
from pathlib import Path

from PyQt6.QtGui import QFontDatabase

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_FILES = ("NotoSansTC-VF.ttf",)
FALLBACK_FAMILY = "Segoe UI"

_loaded_family: str | None = None


def load_app_font() -> str:
    """Register the bundled font with Qt and remember its family name.

    Must be called after QApplication is created. Returns FALLBACK_FAMILY if
    no font file could be loaded.
    """
    global _loaded_family
    family = FALLBACK_FAMILY
    for file_name in _FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(_FONT_DIR / file_name))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family = families[0]
    _loaded_family = family
    return family


def app_font_family() -> str:
    """Family name to use for widget fonts; FALLBACK_FAMILY until loaded."""
    return _loaded_family or FALLBACK_FAMILY
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_fonts.py -v`
Expected: PASS (3 passed). If `test_load_app_font_loads_bundled_noto` fails, the font files in Step 1 are missing or named wrong — fix the filenames.

- [ ] **Step 6: Apply the loaded family in `src/widget.py`**

Add the import near the top of `src/widget.py` (after the existing `from src.lrc_parser import find_current_line`):

```python
from src.fonts import app_font_family
```

After Task 0 removes `_offline_label`, replace the two remaining hardcoded `"Segoe UI"` font constructions:

- `src/widget.py:87` — `self._track_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))`
  →
```python
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
```

- `src/widget.py:111` — `self._lyric_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))`
  →
```python
        self._lyric_label.setFont(QFont(app_font_family(), 16, QFont.Weight.Bold))
```

- [ ] **Step 7: Load the font in `main()` before any widget is built**

In `src/main.py`, add the import alongside the other `src` imports:

```python
from src.fonts import load_app_font
```

In `main()`, immediately after `app.setApplicationName("Spotify Lyrics Widget")` (line 250), add:

```python
    load_app_font()
```

This runs before `App()` constructs `LyricsWidget`, so `app_font_family()` returns the Noto family in the real app.

- [ ] **Step 8: Run the full widget + main test suites to confirm nothing broke**

Run: `pytest tests/test_widget.py tests/test_main.py tests/test_fonts.py -v`
Expected: all PASS. (`test_track_label_font_is_larger_and_demibold` only checks point size ≥ 10 and weight ≥ DemiBold, so the family swap does not affect it.)

- [ ] **Step 9: Visually verify CJK rendering and re-tune the lyric lane height**

Run the app: `python run.pyw` (or `pythonw run.pyw`) and play a track with a Chinese title and Chinese lyrics.
Verify: Chinese glyphs render with Noto Sans TC (clean, not a blocky fallback). Confirm the 2-line lyric lane does NOT clip the second line — Noto's metrics differ from Segoe UI.

If the second line is clipped, increase `LYRIC_LANE_HEIGHT` in `src/widget.py:27` (start at `56`, try `60`, then `64`) until two full lines fit without growing the panel awkwardly. Re-run and re-check. Record the final value.

- [ ] **Step 10: Commit**

```bash
git add assets/fonts/ src/fonts.py src/widget.py src/main.py tests/test_fonts.py
git commit -m "feat: bundle Noto Sans TC and apply to widget fonts (V1.3)"
```

---

## Task 2: System tray icon

**Why:** The widget is frameless and sometimes gets covered; there's no quick way to confirm it's running or pull it to the front. A tray icon is a persistent status light + a one-click "raise" control, reusing the existing `App.raise_window()` (the same logic the single-instance guard already uses). The right-click menu also surfaces the existing `widget.log` (decided: keep the log; add an "Open log file" action — no in-app viewer).

**Files:**
- Create: `src/tray.py`
- Test: `tests/test_tray.py`
- Modify: `src/logging_setup.py` (extract `log_file_path()`)
- Test: `tests/test_logging_setup.py` (add `log_file_path` test)
- Modify: `src/main.py` (`App.start`, `App.shutdown`, new `_toggle_widget` / `_open_log`)
- Test: `tests/test_main.py` (add toggle/open-log tests)

- [ ] **Step 1: Write the failing tests for the tray module**

Create `tests/test_tray.py`:

```python
from PyQt6.QtWidgets import QSystemTrayIcon

from src.tray import TrayIcon, build_tray_icon


def _noop():
    pass


def _make_tray(**overrides):
    callbacks = dict(
        on_activate=_noop, on_toggle=_noop, on_open_log=_noop, on_quit=_noop
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)


def test_build_tray_icon_not_null(qtbot):
    assert not build_tray_icon().isNull()


def test_trigger_calls_on_activate(qtbot):
    calls = []
    tray = _make_tray(on_activate=lambda: calls.append("activate"))
    tray._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert calls == ["activate"]


def test_double_click_does_not_call_on_activate(qtbot):
    calls = []
    tray = _make_tray(on_activate=lambda: calls.append("activate"))
    tray._on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert calls == []


def test_menu_has_open_log_and_quit(qtbot):
    tray = _make_tray()
    labels = [action.text() for action in tray._menu.actions() if action.text()]
    assert "Open log file" in labels
    assert "Quit" in labels


def test_set_widget_visible_updates_toggle_label(qtbot):
    tray = _make_tray()
    tray.set_widget_visible(True)
    assert tray._toggle_action.text() == "Hide widget"
    tray.set_widget_visible(False)
    assert tray._toggle_action.text() == "Show widget"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_tray.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tray'`.

- [ ] **Step 3: Implement `src/tray.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

SPOTIFY_GREEN = "#1DB954"


def build_tray_icon() -> QIcon:
    """A small filled Spotify-green circle, drawn at runtime (no asset file)."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(SPOTIFY_GREEN)))
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)


class TrayIcon:
    """System tray presence: status indicator + raise + context menu."""

    def __init__(self, on_activate, on_toggle, on_open_log, on_quit, parent=None):
        self._on_activate = on_activate
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()
        self._toggle_action = self._menu.addAction("Hide widget")
        self._toggle_action.triggered.connect(lambda: on_toggle())
        self._menu.addAction("Open log file").triggered.connect(lambda: on_open_log())
        self._menu.addSeparator()
        self._menu.addAction("Quit").triggered.connect(lambda: on_quit())
        self._tray.setContextMenu(self._menu)

        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_activate()

    def set_widget_visible(self, visible: bool):
        self._toggle_action.setText("Hide widget" if visible else "Show widget")

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_tray.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Write the failing test for `log_file_path()`**

Add to `tests/test_logging_setup.py`:

```python
def test_log_file_path_under_appdata(monkeypatch, tmp_path):
    from src.logging_setup import log_file_path

    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert log_file_path() == tmp_path / "spotify-lyrics-widget" / "widget.log"
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `pytest tests/test_logging_setup.py::test_log_file_path_under_appdata -v`
Expected: FAIL with `ImportError: cannot import name 'log_file_path'`.

- [ ] **Step 7: Extract `log_file_path()` in `src/logging_setup.py`**

Add the function and have `configure_logging()` reuse it. Replace the body of `configure_logging()` that computes `log_dir` / `log_path` (lines 15–18) so both share one definition:

```python
def log_file_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    return Path(appdata) / LOG_DIR_NAME / LOG_FILE_NAME


def configure_logging() -> Path:
    """Configure file logging before the app hides its console."""
    log_path = log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        if getattr(handler, "_spotify_widget_handler", False):
            root_logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler._spotify_widget_handler = True
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.addHandler(handler)
    return log_path
```

- [ ] **Step 8: Run the logging tests to verify they pass**

Run: `pytest tests/test_logging_setup.py -v`
Expected: all PASS (existing tests + the new one).

- [ ] **Step 9: Write the failing tests for the App wiring**

Add to `tests/test_main.py` (it already defines `_make_app()` and imports `MagicMock`, `patch`):

```python
def test_toggle_widget_hides_when_visible():
    app, _, widget = _make_app()
    app._tray = MagicMock()
    widget.isVisible.return_value = True

    app._toggle_widget()

    widget.hide.assert_called_once()
    app._tray.set_widget_visible.assert_called_once_with(False)


def test_toggle_widget_raises_when_hidden():
    app, _, widget = _make_app()
    app._tray = MagicMock()
    widget.isVisible.return_value = False

    app._toggle_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    app._tray.set_widget_visible.assert_called_once_with(True)


def test_open_log_starts_log_file():
    app, _, _ = _make_app()

    with (
        patch("src.main.log_file_path", return_value="LOGPATH"),
        patch("src.main.os.startfile", create=True) as startfile,
    ):
        app._open_log()

    startfile.assert_called_once_with("LOGPATH")
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `pytest tests/test_main.py::test_toggle_widget_hides_when_visible tests/test_main.py::test_open_log_starts_log_file -v`
Expected: FAIL — `App` has no `_toggle_widget` / `_open_log`, and `src.main` has no `os` / `log_file_path`.

- [ ] **Step 11: Wire the tray into `App` in `src/main.py`**

Add imports at the top of `src/main.py`:

```python
import os
```
and to the `src` import group:
```python
from src.logging_setup import configure_logging, log_file_path
from src.tray import TrayIcon
```
(`configure_logging` is already imported — extend that line to add `log_file_path`.)

In `App.__init__`, add an attribute initializer after `self._current_track_id`:

```python
        self._tray: TrayIcon | None = None
```

In `App.start()`, after `self._widget.show()` (line 118), create and show the tray:

```python
        app = QApplication.instance()
        self._tray = TrayIcon(
            on_activate=self.raise_window,
            on_toggle=self._toggle_widget,
            on_open_log=self._open_log,
            on_quit=app.quit if app is not None else (lambda: None),
        )
        self._tray.set_widget_visible(True)
        self._tray.show()
```

Add the two new methods to `App` (next to `raise_window`):

```python
    def _toggle_widget(self):
        if self._widget.isVisible():
            self._widget.hide()
            if self._tray is not None:
                self._tray.set_widget_visible(False)
        else:
            self._widget.showNormal()
            self._widget.raise_()
            self._widget.activateWindow()
            if self._tray is not None:
                self._tray.set_widget_visible(True)

    def _open_log(self):
        os.startfile(log_file_path())
```

In `App.shutdown()`, hide the tray first so no orphan icon is left (add as the first lines of the method):

```python
        if self._tray is not None:
            self._tray.hide()
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: all PASS.

- [ ] **Step 13: Run the whole suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 14: Manually verify the tray icon — including the Windows raise risk**

Run the app: `pythonw run.pyw`. Then verify each:
1. A green circle appears in the system tray (notification area). Hovering shows the "Spotify Lyrics Widget" tooltip. → confirms running-status indicator.
2. Cover the widget with another window (e.g. maximize a browser over it). **Left-click** the tray icon. The widget should jump to the front. → confirms raise-from-covered.
3. Right-click the tray icon: menu shows "Hide widget" / "Open log file" / "Quit". "Hide widget" hides the widget and the label flips to "Show widget"; clicking again restores it. "Open log file" opens `widget.log` in the default editor. "Quit" exits the app **and the tray icon disappears** (no orphan).
4. Launch a second instance (`pythonw run.pyw` again) while one runs — only one tray icon exists; the second launch raises the first and exits.

**If step 2 fails** (Windows blocks the foreground change and only flashes the taskbar — a known Windows foreground-lock behavior), apply this fallback in `App.raise_window` and re-test:

```python
    def raise_window(self):
        from PyQt6.QtCore import Qt

        self._widget.showNormal()
        # Re-assert always-on-top to force a restack past the covering window.
        self._widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self._widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._widget.show()
        self._widget.raise_()
        self._widget.activateWindow()
```

Note: toggling the flag re-shows the window; confirm it does not move from its saved position. If it does, prefer the original three-line `raise_window` and accept a taskbar flash. Record which version you kept.

- [ ] **Step 15: Commit**

```bash
git add src/tray.py src/logging_setup.py src/main.py tests/test_tray.py tests/test_logging_setup.py tests/test_main.py
git commit -m "feat: add system tray icon (status, raise, log, quit) (V1.3)"
```

---

## Task 3: Start-menu and desktop shortcuts

**Why:** A one-shot installer that drops `.lnk` shortcuts pointing at `pythonw.exe run.pyw`, so the widget launches without a console and is reachable from the Start menu / desktop. No startup-on-boot (roadmap decision: autostart would risk resurrecting the multi-instance / 429 hammering). Uses the Windows-built-in `WScript.Shell` COM object via PowerShell — no third-party dependency.

**Files:**
- Create: `src/shortcuts.py`
- Create: `scripts/install_shortcuts.py`
- Test: `tests/test_shortcuts.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shortcuts.py`:

```python
from pathlib import Path

from src import shortcuts


def test_build_powershell_script_sets_target_args_and_save():
    script = shortcuts.build_powershell_script(
        shortcut_path=r"C:\links\widget.lnk",
        target=r"C:\venv\Scripts\pythonw.exe",
        arguments=r"C:\app\run.pyw",
        working_dir=r"C:\app",
    )
    assert r"CreateShortcut('C:\links\widget.lnk')" in script
    assert r"$s.TargetPath = 'C:\venv\Scripts\pythonw.exe'" in script
    assert r"$s.Arguments = 'C:\app\run.pyw'" in script
    assert r"$s.WorkingDirectory = 'C:\app'" in script
    assert "$s.Save()" in script


def test_pythonw_path_is_sibling_of_executable(monkeypatch):
    monkeypatch.setattr(shortcuts.sys, "executable", r"C:\venv\Scripts\python.exe")
    assert shortcuts.pythonw_path() == Path(r"C:\venv\Scripts\pythonw.exe")


def test_shortcut_locations_name_and_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    locations = shortcuts.shortcut_locations()
    assert locations["desktop"].name == "Spotify Lyrics Widget.lnk"
    assert locations["start_menu"].name == "Spotify Lyrics Widget.lnk"
    assert "Start Menu" in str(locations["start_menu"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_shortcuts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.shortcuts'`.

- [ ] **Step 3: Implement `src/shortcuts.py`**

```python
import os
import subprocess
import sys
from pathlib import Path

SHORTCUT_NAME = "Spotify Lyrics Widget.lnk"


def build_powershell_script(
    shortcut_path: str, target: str, arguments: str, working_dir: str
) -> str:
    return "\n".join(
        [
            "$ws = New-Object -ComObject WScript.Shell",
            f"$s = $ws.CreateShortcut('{shortcut_path}')",
            f"$s.TargetPath = '{target}'",
            f"$s.Arguments = '{arguments}'",
            f"$s.WorkingDirectory = '{working_dir}'",
            "$s.Save()",
        ]
    )


def pythonw_path() -> Path:
    """The windowed interpreter next to the current python.exe (venv-safe)."""
    return Path(sys.executable).with_name("pythonw.exe")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def shortcut_locations() -> dict[str, Path]:
    desktop = Path.home() / "Desktop"
    start_menu = (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )
    return {
        "desktop": desktop / SHORTCUT_NAME,
        "start_menu": start_menu / SHORTCUT_NAME,
    }


def create_shortcuts() -> list[Path]:
    """Create Start-menu and desktop shortcuts to `pythonw run.pyw`."""
    target = str(pythonw_path())
    arguments = str(project_root() / "run.pyw")
    working_dir = str(project_root())

    created = []
    for location in shortcut_locations().values():
        location.parent.mkdir(parents=True, exist_ok=True)
        script = build_powershell_script(
            str(location), target, arguments, working_dir
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
        )
        created.append(location)
    return created
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_shortcuts.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Create the one-shot entry point `scripts/install_shortcuts.py`**

```python
from src.shortcuts import create_shortcuts

if __name__ == "__main__":
    for path in create_shortcuts():
        print(f"Created: {path}")
```

- [ ] **Step 6: Manually verify shortcuts are created and launch the widget**

Run from the project root **using the interpreter that has PyQt6 installed** (so its sibling `pythonw.exe` is the right one):

Run: `python scripts/install_shortcuts.py`
Expected: prints two `Created:` lines (desktop + Start menu).

Then: double-click the new desktop "Spotify Lyrics Widget" shortcut. The widget launches with **no console window**. Confirm the Start-menu entry appears under All apps and also launches it. Confirm no startup-on-boot entry was added (nothing in `shell:startup`).

- [ ] **Step 7: Commit**

```bash
git add src/shortcuts.py scripts/install_shortcuts.py tests/test_shortcuts.py
git commit -m "feat: add Start-menu/desktop shortcut installer (V1.3)"
```

---

## Self-Review

**Spec coverage** (against the roadmap V1.3 line: ① shortcut no-autostart, ② Noto Sans TC font, ③ tray icon with status / raise / right-click menu incl. open-log, ④ offline status in lyric lane):
- ① shortcut, no startup-on-boot → Task 3 (verified in Step 6 that `shell:startup` stays empty).
- ② Noto Sans TC for title + lyric, re-tune lane height → Task 1 (Steps 6, 9).
- ③ tray icon: status indicator → Task 2 Step 14.1; left-click raise → Step 14.2 (+ documented Windows foreground fallback); right-click menu Show/Hide, Open log, Quit → Steps 3, 14.3; no orphan icon on quit → `shutdown` hide + Step 14.3; single-instance still one icon → Step 14.4.
- ④ offline status in lyric lane, no right-top overlay → Task 0.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to" placeholders. The only deferred-to-runtime value is `LYRIC_LANE_HEIGHT` (Task 1 Step 9) — unavoidable visual tuning, given a concrete starting value (56) and try-sequence (60, 64).

**Type/name consistency:** `app_font_family()` defined in Task 1 and used in `widget.py` (Task 1) and `main.py` loads via `load_app_font()`. `TrayIcon(on_activate, on_toggle, on_open_log, on_quit)` signature in Task 2 Step 3 matches the call site in Step 11 and the test factory in Step 1. `log_file_path()` defined in Task 2 Step 7, used in `main.py` Step 11 and patched in the Step 9 test. `build_powershell_script`, `pythonw_path`, `shortcut_locations`, `create_shortcuts` names consistent across Task 3 module, tests, and entry point.

**Cross-feature note:** Task 0 should run before V2 so the top row is clean. Tasks 1/2/3 are otherwise independent and can be implemented and committed in any order; the order above (offline → font → tray → shortcuts) goes simplest-self-contained first.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-spotify-lyrics-widget-v1-3.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
