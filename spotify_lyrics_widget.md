# Spotify 歌詞懸浮視窗 — 開發交接文件

最後更新：2026年6月6日

目前版本：V2.02（LRCLIB unavailable → NetEase salvage patch）

---

## 專案目的

這是一個 Windows 自用 Spotify 歌詞懸浮視窗。目標是不用切回 Spotify App，也能在桌面最上層看到目前歌曲、同步歌詞、播放進度，並能用小型控制列操作上一首、播放/暫停、下一首。

---

## 目前已完成

- 固定 `420x112` 的 PyQt6 懸浮視窗，永遠在最上層，可拖曳
- Windows 11 DWM 圓角與 Spotify 綠色系統邊框
- Spotify OAuth PKCE 授權與 token refresh
- 每秒 poll Spotify currently-playing，更新歌名、歌手、播放狀態、進度條
- LRCLIB 作為主要同步歌詞來源
- NetEase 作為 fallback：LRCLIB 確認沒有同步歌詞時啟用；LRCLIB 暫時不可用時也會補救查一次
- 歌詞 transient failure 不寫入 no-lyrics cache，避免暫時 timeout 變成永久無歌詞
- 中文歌詞 fallback 會做 Traditional/Simplified matching，顯示時轉為繁體
- system tray：Show/Hide、Open log file、Quit
- single-instance guard：重複開啟會聚焦既有視窗，不開第二個
- `run.pyw` 無 console 啟動，錯誤寫入 log
- V2 hover-only 播放控制：上一首、播放/暫停、下一首
- 長歌名 hover marquee，未 hover 時 elide
- V2.01 歌詞顯示最多兩個視覺行，過長時截斷為 `...`
- V2.01 在 Spotify 已有可用 device 但 not playing 時，播放按鈕會嘗試指定 device 開始播放
- V2.02 在 LRCLIB timeout / 暫時不可用時，NetEase 會補救查一次；若 NetEase 也沒找到，不會把這首歌記成永久無歌詞

最新完整測試紀錄：`206 passed`（2026-06-06）

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

## 建議下一步

1. 用 `master` 做 V2.02 最後實機確認。
2. 視需要補 Phase B 更詳細 log：device fallback start / selected device / retry success。
3. 若主要功能穩定，再進 V3：PyInstaller 打包、first-run UX、捷徑/資源路徑整理。
