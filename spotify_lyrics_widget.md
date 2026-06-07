# Spotify 歌詞懸浮視窗 — 開發交接文件

最後更新：2026年6月7日

目前實作版本：V2.04（three size presets: Small / Medium / Large，已 merge 到 `master`）

下一步：進入 V3 前置整理：GitHub 開源文件、PyInstaller 打包、first-run UX。

---

## 專案目的

這是一個 Windows 自用 Spotify 歌詞懸浮視窗。目標是不用切回 Spotify App，也能在桌面最上層看到目前歌曲、同步歌詞、播放進度，並能用小型控制列操作上一首、播放/暫停、下一首。

---

## 目前已完成

- PyQt6 懸浮視窗，永遠在最上層，可拖曳；支援 Small (300x74)、Medium (360x90)、Large (420x112) 三種固定密度尺寸
- Windows 11 DWM 圓角與 Spotify 綠色系統邊框
- Spotify OAuth PKCE 授權與 token refresh
- 每秒 poll Spotify currently-playing，更新歌名、歌手、播放狀態、進度條
- LRCLIB 作為主要同步歌詞來源
- NetEase 作為 fallback：LRCLIB 確認沒有同步歌詞時啟用；LRCLIB 暫時不可用時也會補救查一次
- 歌詞 transient failure 不寫入 no-lyrics cache，避免暫時 timeout 變成永久無歌詞
- 中文歌詞 fallback 會做 Traditional/Simplified matching，顯示時轉為繁體
- system tray：左鍵 toggle widget 顯示/隱藏，右鍵 menu 有 Size submenu（Small / Medium / Large）和 Quit
- single-instance guard：重複開啟會聚焦既有視窗，不開第二個
- `run.pyw` 無 console 啟動，錯誤寫入 log
- V2 hover-only 播放控制：上一首、播放/暫停、下一首
- 長歌名 hover marquee，未 hover 時 elide
- V2.01 歌詞顯示最多兩個視覺行，過長時截斷為 `...`
- V2.01 在 Spotify 已有可用 device 但 not playing 時，播放按鈕會嘗試指定 device 開始播放
- V2.02 在 LRCLIB timeout / 暫時不可用時，NetEase 會補救查一次；若 NetEase 也沒找到，不會把這首歌記成永久無歌詞
- V2.03 size presets：tray menu 可切換 Current / Compact / Small / Mini 四種固定密度尺寸；所有 preset 歌詞顯示兩行；選擇會持久化到 config
- V2.03 tray 精簡：移除 Show/Hide 和 Open log file，左鍵點 tray icon 直接 toggle widget 顯示/隱藏
- V2.03 optimistic play/pause：點擊播放/暫停按鈕後立刻翻轉 icon 狀態，不等 API 回應
- V2.04 three size presets：收斂為 Small / Medium / Large 三種尺寸；舊 `mini / compact / current` config key 會 alias 到新值，`small` 直接代表 V2.04 新 Small

最新完整測試紀錄：`224 passed`（2026-06-07）

---

## 技術選型

**語言：** Python 3.12

**GUI：** PyQt6

**HTTP：** httpx

**測試：** pytest、pytest-qt

**文字處理：** zhconv（NetEase fallback 的簡繁比對與顯示）

---

## 外部 API

- Spotify Web API
  - `GET /v1/me/player/currently-playing`
  - `PUT /v1/me/player/play`
  - `PUT /v1/me/player/pause`
  - `POST /v1/me/player/previous`
  - `POST /v1/me/player/next`
  - `GET /v1/me/player/devices`
- LRCLIB
  - 主要同步 LRC 歌詞來源
  - timeout / non-200 / malformed JSON 視為暫時 unavailable
- NetEase public endpoint
  - LRCLIB confirmed miss 後 fallback
  - LRCLIB 暫時 unavailable 時也會補救查一次
  - 非官方來源，已有 cooldown 與 concrete logging

目前沒有使用 Genius fallback。

---

## Spotify scopes

目前需要：

```text
user-read-currently-playing
user-modify-playback-state
user-read-playback-state
```

如果本機 config 裡的 `granted_scope` 缺少新 scope，啟動時會重新走 Spotify 授權。

---

## 核心流程

1. 啟動時確保只有單一 instance。
2. 載入 `%APPDATA%/spotify-lyrics-widget/config.json`。
3. 檢查 token 與 granted scopes，必要時 refresh 或重新 OAuth。
4. 每秒 poll Spotify currently-playing。
5. track ID 改變時清空舊歌詞，背景查 LRCLIB。
6. LRCLIB confirmed miss 時，再查 NetEase fallback。
7. LRCLIB 暫時 unavailable 時，也會查 NetEase 補救一次。
8. UI tick 依照 Spotify progress 選出目前歌詞行。
9. 顯示層把歌詞限制在最多兩個視覺行。
10. hover 時顯示播放控制與長歌名 marquee。
11. Quit 時停止 worker/thread，移除 tray icon。

---

## 重要路徑

- Config：`%APPDATA%/spotify-lyrics-widget/config.json`
- Log：`%APPDATA%/spotify-lyrics-widget/widget.log`
- 入口：`run.pyw`
- 主程式：`src/main.py`
- UI：`src/widget.py`
- 播放控制：`src/playback.py`
- 歌詞 worker：`src/lyrics_worker.py`
- LRCLIB parser：`src/lrc_parser.py`
- NetEase fallback：`src/netease.py`
- 歌詞兩行 clamp：`src/lyric_clamp.py`

---

## 目前限制與 deferred

- 尚未打包成 single `.exe`
- 尚未做 first-run UX
- 尚未做 playlist add / default playlist
- 不做 startup-on-boot，除非重新驗證 single-instance 與 rate-limit brake
- 不做 content-driven auto-resize，避免重現 UI 跳動
- 不支援 Mac / Linux
- 不做 Genius / Musixmatch / private Spotify cookie fallback
- 歌詞翻譯與雙語顯示暫不做

---

## V2.03 size preset（已完成）

Branch `codex/v2.03-size-presets`，worktree `.worktrees/v2.03-size-presets`。

實作內容：

- `src/config.py`：新增 `size_preset` 持久化欄位，預設 `current`
- `src/lyric_clamp.py`：支援 `max_lines=1` 的單行省略
- `src/transport_button.py`：`set_button_size()` 讓 button 可縮放
- `src/widget.py`：`SIZE_PRESETS` dataclass、`apply_size_preset()` 套用寬高/字體/layout/button size/lyric lines
- `src/tray.py`：`Size` submenu，checked action group
- `src/main.py`：啟動時套用 config preset，tray 選擇即時套用並保存

文件：

- Spec：`docs/superpowers/specs/2026-06-06-spotify-widget-size-presets-design.md`
- Plan：`docs/superpowers/plans/2026-06-06-spotify-widget-size-presets.md`

---

## V2.04 three size presets（已完成並 merge 到 master）

V2.03 實機觀察後，四段尺寸過細，且 Compact / Small 的間距不像同一套均勻階梯。V2.04 決定收斂成三段：

- Small：原 Mini，`300x74`
- Medium：原 Compact / Small 合併，`360x90`
- Large：原 Current，`420x112`，也是預設

Config 允許值已改成 `small / medium / large`，不新增額外 config 版本欄位。V2.04 直接重排 preset table；舊 config 裡已存在的 `small` 會被當成 V2.04 新 Small。移除的舊 key 用簡單 alias：

- `mini` → `small`
- `compact` → `medium`
- `current` → `large`

實作 branch：`codex/v2.04-three-size-presets`，已 merge 到 `master`

主要 commits：

- `efd7323` — `feat: normalize three widget size presets`
- `a1dec48` — `feat: collapse widget size presets to three`
- `92b1402` — `feat: update tray size preset actions`
- `42f12b2` — `test: use three size preset names in app flow`
- `cacee90` — `fix: keep small preset height after layout activation`
- `dce5da0` — `Merge V2.04 three size presets into master`

驗證：

- Focused suite：`87 passed`
- Full suite：`224 passed`

文件：

- Spec：`docs/superpowers/specs/2026-06-07-spotify-widget-three-size-presets-design.md`
- Plan：`docs/superpowers/plans/2026-06-07-spotify-widget-three-size-presets.md`

實機 review 結果：Small / Medium / Large 切換正常。曾發現 Large / Medium 切到 Small 時高度會短暫回到舊 layout；根因是 `apply_size_preset()` 太早 `setFixedSize()`，後續 layout activation 又排入 stale resize。修正為 layout activation 後再鎖定 fixed size。

---

## 建議下一步

1. 開源前補 `README.md` / `LICENSE` / 使用者安裝與 Spotify App 設定教學。
2. V3：PyInstaller 打包、first-run UX、捷徑/資源路徑整理。
3. 打包後處理 antivirus false-positive / signing。
