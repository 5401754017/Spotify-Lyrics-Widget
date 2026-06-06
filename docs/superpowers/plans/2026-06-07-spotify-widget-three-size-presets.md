# Spotify Widget Three Size Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 V2.03 的 Current / Compact / Small / Mini 四段尺寸收斂成 Small / Medium / Large 三段尺寸。

**Architecture:** `src/widget.py` 直接把 preset table 重排成 Small / Medium / Large。`src/config.py` 只做簡單 alias normalization：`mini -> small`、`compact -> medium`、`current -> large`；`small` 保持 `small`，不保留 V2.03 舊 Small 的語意。`src/tray.py` 只顯示 Small / Medium / Large；`src/main.py` 維持既有 callback/save wiring，但測試要改成新 preset values。

**Tech Stack:** Python 3.12, PyQt6, pytest, pytest-qt.

---

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `src/config.py` | Modify | 預設 `large`，簡單 normalize removed preset keys |
| `src/widget.py` | Modify | `SIZE_PRESETS` 改成 `small / medium / large` 三個 profile |
| `src/tray.py` | Modify | `SIZE_ACTIONS` 改成 Small / Medium / Large |
| `tests/test_config.py` | Modify | 測 default、removed key aliases、`small` 保持新 Small |
| `tests/test_widget.py` | Modify | 測三個 preset 的尺寸、font、line count、slot 順序 |
| `tests/test_tray.py` | Modify | 測 tray menu 三個 label 與 callback |
| `tests/test_main.py` | Modify | 測 startup / tray save 使用新 preset values |
| `spotify_lyrics_widget.md` | Modify | 記錄 V2.04 正在實作或完成狀態 |
| `docs/superpowers/plans/2026-05-25-roadmap.md` | Modify | 加 V2.04 roadmap row |

All pytest commands should keep using the repo's safe temp/cache flags:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04 -q <args>
```

---

## Task 1: Config Uses Three Preset Names

**Why:** V2.04 只保留 `small / medium / large`。舊 `mini / compact / current` 可以用簡單 alias 對到新 key；`small` 不轉換，直接代表 V2.04 新 Small。

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add failing config tests**

In `tests/test_config.py`, add `import pytest` near the top if it is not present.

Replace the existing size preset tests with:

```python
def test_size_preset_defaults_to_large(tmp_path):
    config = Config(config_dir=tmp_path)

    assert config.size_preset == "large"


def test_size_preset_persists_new_small_value(tmp_path):
    config = Config(config_dir=tmp_path)
    config.size_preset = "small"
    config.save()

    config2 = Config(config_dir=tmp_path)

    assert config2.size_preset == "small"


@pytest.mark.parametrize(
    ("removed_value", "expected"),
    [
        ("mini", "small"),
        ("compact", "medium"),
        ("current", "large"),
    ],
)
def test_removed_size_preset_values_use_simple_alias(tmp_path, removed_value, expected):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"size_preset": removed_value}))

    config = Config(config_dir=tmp_path)

    assert config.size_preset == expected


def test_existing_small_value_is_treated_as_new_small(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"size_preset": "small"}))

    config = Config(config_dir=tmp_path)

    assert config.size_preset == "small"
```

- [ ] **Step 2: Run config tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_config -q tests/test_config.py -k size_preset -v
```

Expected: FAIL because default is still `current` and aliases do not exist.

- [ ] **Step 3: Implement config normalization**

In `src/config.py`, add constants above `class Config`:

```python
SIZE_PRESET_VALUES = {"small", "medium", "large"}
SIZE_PRESET_ALIASES = {
    "mini": "small",
    "compact": "medium",
    "current": "large",
}
```

Update `_DEFAULTS`:

```python
        "size_preset": "large",
```

Add a helper inside `Config`:

```python
    def _normalize_size_preset(self, data: dict) -> str:
        raw_value = data.get("size_preset", self._DEFAULTS["size_preset"])
        if raw_value in SIZE_PRESET_VALUES:
            return raw_value
        return SIZE_PRESET_ALIASES.get(raw_value, "large")
```

In `_load()`, after the existing loop, set normalized values:

```python
        self.size_preset = self._normalize_size_preset(data)
```

Keep `save()` unchanged.

- [ ] **Step 4: Run config tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_config -q tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/config.py tests/test_config.py
git commit -m "feat: normalize three widget size presets"
```

---

## Task 2: Widget Uses Small / Medium / Large

**Why:** Widget preset profile 是尺寸行為核心。V2.04 只允許三段固定 profile。

**Files:**
- Modify: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Update widget tests first**

In `tests/test_widget.py`, update size preset tests to expect:

```python
def test_widget_defaults_to_large_size_preset(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert widget.size_preset == "large"
    assert widget.size().width() == 420
    assert widget.size().height() == 112


def test_widget_has_three_size_presets(qtbot):
    from src.widget import SIZE_PRESETS

    assert list(SIZE_PRESETS) == ["small", "medium", "large"]


def test_widget_applies_all_size_presets(qtbot):
    from src.widget import SIZE_PRESETS, LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    expected_sizes = {
        "small": (300, 74, 8, 10, 2),
        "medium": (360, 90, 9, 13, 2),
        "large": (420, 112, 10, 16, 2),
    }

    for name, preset in SIZE_PRESETS.items():
        widget.apply_size_preset(name)
        width, height, title_pt, lyric_pt, lyric_lines = expected_sizes[name]
        assert (preset.width, preset.height) == (width, height)
        assert widget.size().width() == width
        assert widget.size().height() == height
        assert widget._track_label.font().pointSize() == title_pt
        assert widget._lyric_label.font().pointSize() == lyric_pt
        assert widget._max_lyric_visual_lines == lyric_lines
```

Keep `test_widget_mini_clamps_lyric_to_two_lines` but rename it to:

```python
def test_widget_small_clamps_lyric_to_two_lines(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.apply_size_preset("small")
    widget.show()
    qtbot.waitExposed(widget)

    widget.set_lyric_text(
        "You look away from me and I see something you are trying to hide"
    )

    assert widget._lyric_label.text().count("\n") <= 1
    assert widget._max_lyric_visual_lines == 2
```

- [ ] **Step 2: Run widget tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_widget -q tests/test_widget.py -k "size_preset or three_size_presets or small_clamps" -v
```

Expected: FAIL because widget still has `current / compact / small / mini`.

- [ ] **Step 3: Update `SIZE_PRESETS`**

In `src/widget.py`, replace `SIZE_PRESETS` with:

```python
SIZE_PRESETS = {
    "small": WidgetSizePreset(
        "small", 300, 74, 6, 18, 2, 41, 2, 1, 4,
        10, 198, 8, 56, 22, 6, 18, 18, 6,
        8, 10, 2, QSize(16, 22), 4, 12,
    ),
    "medium": WidgetSizePreset(
        "medium", 360, 90, 8, 21, 4, 48, 3, 1, 5,
        13, 237, 11, 62, 23, 9, 19, 19, 9,
        9, 13, 2, QSize(17, 23), 5, 13,
    ),
    "large": WidgetSizePreset(
        "large", 420, 112, 12, 24, 5, 56, 5, 2, 8,
        16, 282, 14, 66, 24, 12, 20, 20, 10,
        10, 16, 2, QSize(18, 24), 6, 14,
    ),
}
DEFAULT_SIZE_PRESET = "large"
```

- [ ] **Step 4: Run widget focused suite green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_widget -q tests/test_widget.py tests/test_transport_button.py tests/test_lyric_clamp.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/widget.py tests/test_widget.py
git commit -m "feat: collapse widget size presets to three"
```

---

## Task 3: Tray Shows Three Presets

**Why:** User-facing menu must match the new preset names.

**Files:**
- Modify: `src/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Update tray tests first**

In `tests/test_tray.py`, update defaults and expectations:

```python
def _make_tray(**overrides):
    callbacks = dict(
        on_toggle=_noop,
        on_quit=_noop,
        on_size_changed=_noop,
        size_preset="large",
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)
```

Replace `test_menu_has_size_submenu_with_presets` with:

```python
def test_menu_has_size_submenu_with_presets(qtbot):
    tray = _make_tray(on_size_changed=lambda name: None, size_preset="medium")

    size_actions = [
        action for action in tray._menu.actions()
        if action.menu() is not None and action.text() == "Size"
    ]
    assert len(size_actions) == 1

    labels = [action.text() for action in tray._size_menu.actions()]
    assert labels == ["Small", "Medium", "Large"]
    checked = [action.text() for action in tray._size_menu.actions() if action.isChecked()]
    assert checked == ["Medium"]
```

Replace `test_size_action_calls_callback` with:

```python
def test_size_action_calls_callback(qtbot):
    calls = []
    tray = _make_tray(on_size_changed=lambda name: calls.append(name))

    small_action = next(
        action for action in tray._size_menu.actions() if action.text() == "Small"
    )
    small_action.trigger()

    assert calls == ["small"]
```

- [ ] **Step 2: Run tray tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_tray -q tests/test_tray.py -k size -v
```

Expected: FAIL because tray still shows Current / Compact / Small / Mini.

- [ ] **Step 3: Update tray actions**

In `src/tray.py`, replace `SIZE_ACTIONS` with:

```python
SIZE_ACTIONS = [
    ("Small", "small"),
    ("Medium", "medium"),
    ("Large", "large"),
]
```

Update `TrayIcon.__init__` default:

```python
        size_preset: str = "large",
```

- [ ] **Step 4: Run tray tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_tray -q tests/test_tray.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/tray.py tests/test_tray.py
git commit -m "feat: show three size presets in tray"
```

---

## Task 4: Main Tests Use Canonical Values

**Why:** Existing wiring should keep working, but tests must prove `App` passes and saves `small / medium / large`.

**Files:**
- Modify: `tests/test_main.py`

- [ ] **Step 1: Update main tests**

In `tests/test_main.py`:

- Change `test_app_applies_config_size_preset_on_init` from `mini` to `small`.
- Change `test_start_creates_tray_with_size_preset` from `small` to `medium`.
- Change `test_size_preset_change_updates_widget_and_config` from `mini` to `small`.

The final expectations should include:

```python
widget.apply_size_preset.assert_called_once_with("small")
assert config.size_preset == "small"
app._tray.set_size_preset.assert_called_once_with("small")
```

- [ ] **Step 2: Run main focused tests**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_main -q tests/test_main.py -k "size_preset or start_creates_tray" -v
```

Expected: PASS. If this fails because production code writes a removed preset value, fix `src/main.py` to use `self._widget.size_preset` after `apply_size_preset()`.

- [ ] **Step 3: Commit Task 4**

```powershell
git add tests/test_main.py src/main.py
git commit -m "test: use new size preset names"
```

---

## Task 5: Docs + Verification

**Why:** V2.04 is a user-visible preset naming and sizing change.

**Files:**
- Modify: `spotify_lyrics_widget.md`
- Modify: `docs/superpowers/plans/2026-05-25-roadmap.md`

- [ ] **Step 1: Run focused suite**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_focus -q tests/test_config.py tests/test_widget.py tests/test_tray.py tests/test_main.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_04_full -q
```

Expected: all tests PASS.

- [ ] **Step 3: Update handoff**

In `spotify_lyrics_widget.md`, update:

- Last updated date to `2026年6月7日`.
- Current version to `V2.04（three size presets: Small / Medium / Large）`.
- Completed list from Current / Compact / Small / Mini to Small / Medium / Large.
- Latest test record from Step 2.
- Add V2.04 section pointing to:
  - Spec: `docs/superpowers/specs/2026-06-07-spotify-widget-three-size-presets-design.md`
  - Plan: `docs/superpowers/plans/2026-06-07-spotify-widget-three-size-presets.md`

- [ ] **Step 4: Update roadmap**

In `docs/superpowers/plans/2026-05-25-roadmap.md`, add V2.04 under Current state and roadmap table:

```markdown
- **V2.04** — Three size presets:
  - Replaces Current / Compact / Small / Mini with Small (300x74), Medium (360x90), Large (420x112).
  - Removed V2.03 config keys use simple aliases: mini -> small, compact -> medium, current -> large.
  - Existing `small` values stay `small`, which means V2.04's new Small.
```

Roadmap row:

```markdown
| **V2.04** | Three size presets. Size menu now shows Small, Medium, and Large. Removed V2.03 config keys use simple aliases; `small` stays the new Small. |
```

- [ ] **Step 5: Commit Task 5**

```powershell
git add spotify_lyrics_widget.md docs/superpowers/plans/2026-05-25-roadmap.md
git commit -m "docs: record V2.04 three size presets"
```

---

## Self-Review

**Spec coverage:**

- Three presets only: Tasks 2 and 3.
- Small keeps old Mini: Task 2.
- Large keeps old Current: Task 2.
- Medium replaces the old Compact / Small middle range: Task 2.
- Removed-key alias normalization without extra config version field: Task 1.
- Tray menu labels: Task 3.
- Main persistence wiring: Task 4.
- Docs and verification: Task 5.

**Placeholder scan:** No placeholder markers. Every task includes test command, expected result, and concrete code or exact edits.

**Type consistency:**

- Accepted values: `small`, `medium`, `large`.
- UI labels: `Small`, `Medium`, `Large`.
- Default preset: `large`.
- No extra config version field.

## Execution Handoff

Plan complete. Recommended execution is **Inline Execution** in this session because the change is small, touches shared widget/tray/config tests, and should be followed by visual review of the three actual sizes.
