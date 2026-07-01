# Spotify Widget Controller Lifecycle Handoff

> 狀態：歷史 handoff。這份交接描述的是 2026-06-23 當時尚未完成的 controller lifecycle 工作；目前狀態請以 `spotify_lyrics_widget.md`、`docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md` 和 `docs/superpowers/plans/2026-06-23-spotify-widget-controller-lifecycle.md` 為準。

## 接手位置

- Worktree：`C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host`
- Branch：`codex/taskbar-host`
- 最新功能方向：taskbar controller 小窗管理 widget lifecycle。
- Canonical spec：`docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md`
- Canonical plan：`docs/superpowers/plans/2026-06-23-spotify-widget-controller-lifecycle.md`
- 已取代 plan：`docs/superpowers/plans/2026-06-22-spotify-widget-taskbar-control-window.md`

## 目前程式狀態

- 目前 code 還是舊版方案 B：`TaskbarHostWindow` 只有 `Widget: Visible/Hidden`、`Show/Hide Widget`、`Quit`。
- 目前 code 的 `widget.close_requested`、controller `quit_requested`、tray `Quit` 都連到 `QApplication.quit`。
- 使用者手動 QA 發現第 8 點失敗：quit 之後 tray、taskbar 都還在，體感像只有 hide widget。
- 這次文件更新尚未改 code；下一個對話要依 canonical plan 實作。

## 定版語意

不要用模糊的「關閉整體程式」。請使用這些名詞：

- Controller：控制窗 + taskbar entry。
- Widget：歌詞 floating widget + workers + tray 代表的 widget session。
- Tray icon：綁定 widget running 狀態，不綁定 controller。

狀態：

```text
Stopped:
Widget: Stopped
Widget: Hidden
[Widget Disabled] disabled    [Run Widget]
tray hidden

Running + Visible:
Widget: Running
Widget: Visible
[Hide Widget]                 [Close Widget]
tray visible

Running + Hidden:
Widget: Running
Widget: Hidden
[Show Widget]                 [Close Widget]
tray visible
```

控制規則：

- `Run Widget`：只由 controller 執行。
- `Show/Hide Widget`：controller left button、widget hide button、tray icon click。
- `Close Widget`：controller right button、widget close、tray menu `Close Widget`。
- Controller X：先 close widget，再關閉 controller/taskbar entry。
- `Widget Disabled` 是 disabled button 的實際文字，不是灰掉的 `Show Widget`。

## 下一步

1. 先讀 canonical spec 與 canonical plan。
2. 用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐 task 實作。
3. 先改 tests，再改 code。
4. 主要會改 `src/taskbar_host.py`、`src/tray.py`、`src/main.py`、`tests/test_taskbar_host.py`、`tests/test_main.py`。
5. 跑 `python -m pytest -q`。
6. Build：`python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec`。
7. 啟動 worktree build：`C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host\dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe`。
8. 依 canonical plan 的手動 QA 清單讓使用者驗證。

## 注意事項

- 不要清理 icon 或 build artifacts；使用者說等定案後再統一清理。
- 不要改 installer，除非使用者明確切回 installer 工作。
- 不要動 master；這個 feature 繼續在 `codex/taskbar-host` worktree。
- 背景程式相關變更要保留 lifecycle/shutdown log，避免 future debugging 沒證據。
