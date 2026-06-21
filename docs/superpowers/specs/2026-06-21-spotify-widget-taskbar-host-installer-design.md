# Spotify Widget Taskbar Host 與 Installer 設計

## 背景

目前 `SpotifyLyricsWidget.exe` 比較像 tray + floating widget。歌詞視窗使用
`Qt.Tool`，這讓它像小工具一樣浮在桌面上，但 Windows 通常不會把這種工具視窗
放進 taskbar。只靠 tray icon 的問題是：使用者可能按了隱藏，之後忘記 app 還在
背景跑，也可能不知道要去系統匣找。

新的目標不是把歌詞 widget 變成一般視窗，而是讓 app 執行中時，Windows taskbar
永遠有一個入口。使用者點 taskbar 入口時，歌詞 widget 會被叫回來。

## 目標

- App 執行中時，taskbar 永遠有 `Spotify Lyrics Widget` 圖示。
- 歌詞 widget 保留目前的小工具行為：frameless、always-on-top、`Qt.Tool`。
- Widget 被隱藏時，taskbar 圖示仍保留，避免使用者以為 app 消失。
- 點 taskbar entry 時，顯示並 raise 歌詞 widget。
- Tray icon 保留現有功能，仍可切換 widget、退出 app。
- Installer 建立 Start Menu shortcut，並提供 Desktop shortcut 選項。
- Installer 寫入正常解除安裝資訊，讓使用者能從 Windows 設定解除安裝。

## 非目標

- 不自動 pin 到 taskbar。Windows 不鼓勵 app/installer 強制釘選。
- 不把歌詞 widget 改成一般標題列視窗。
- 不做開機自啟動。
- 第一版不做 MSIX、code signing 或 Microsoft Store 發佈。
- 第一版不改 `%APPDATA%/spotify-lyrics-widget/` 的 config/log 位置。

## Taskbar Host Window

新增一個同一個 process 內的 `TaskbarHostWindow`。它是一個正常 top-level window，
不使用 `Qt.Tool`，用途是讓 Windows taskbar 有穩定入口。

```text
SpotifyLyricsWidget.exe
+-- LyricsWidget
|   +-- Qt.Tool
|   +-- floating / frameless / always-on-top
|   +-- 可以 show 或 hide
|
+-- TrayIcon
|   +-- 系統匣入口
|   +-- show/hide/quit
|
+-- TaskbarHostWindow
    +-- 一般 top-level window
    +-- showMinimized()
    +-- taskbar 常駐入口
    +-- 被還原時叫回 LyricsWidget
```

預期行為：

```text
啟動 app
-> host showMinimized()
-> taskbar 出現 app 圖示
-> widget 顯示

按 widget 的 hide
-> widget.hide()
-> host 仍 minimized
-> taskbar 圖示仍存在

點 taskbar 圖示
-> host 被 Windows 還原或 activated
-> host emit activated
-> App.raise_window() 顯示/raise widget
-> host 重新 minimize，保留 taskbar entry

taskbar 右鍵 Close window
-> 視為使用者要結束 app
-> QApplication.quit()
```

這個 host 不能完全 hidden，否則 Windows 可能不會在 taskbar 顯示它。第一版採用
`showMinimized()`，讓它存在於 taskbar，但不顯示一個空白主視窗。

如果實測發現最小化 host 會閃出空白窗，就改成第二方案：host 還原時顯示一個小型
控制窗，只放 `Show Widget` 和 `Quit`。這比較像一般 app，但會多一個可見視窗。

## Windows App ID

Windows taskbar 的 icon、分組、shortcut 關聯常依賴 AppUserModelID。啟動時應在建立
Qt 視窗前設定固定 ID：

```text
crayo.SpotifyLyricsWidget
```

這能降低 taskbar icon 不一致、exe 和 shortcut 分組異常的機率。非 Windows 平台不做事。

## Installer

Installer 第一版使用 Inno Setup。原因是它適合傳統 Windows desktop app，能直接產生
`setup.exe`，並處理 Start Menu shortcut、Desktop shortcut、uninstaller 與 Apps 設定頁顯示。

Installer 內容：

- 安裝目前 PyInstaller one-folder output。
- Start Menu 建立 `Spotify Lyrics Widget` shortcut。
- Desktop shortcut 作為 installer task，預設可勾選。
- Shortcut 指向安裝後的 `SpotifyLyricsWidget.exe`。
- 使用 `assets/app-icon.ico` 作為 installer 和 shortcut icon。
- 安裝完成可選擇 launch app。
- 不建立 startup-on-boot shortcut。
- 不做 taskbar pin。

建議新增檔案：

- `installer/SpotifyLyricsWidget.iss`
- `scripts/build_installer.ps1`
- `tests/test_installer.py`

`build_installer.ps1` 只負責驗證 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`
存在，然後呼叫 Inno Setup compiler。它不刪 portable build，也不自動清理舊 installer。

## 測試計畫

自動測試：

- `TaskbarHostWindow` window flags 不包含 `Qt.Tool`。
- `TaskbarHostWindow.show_taskbar_entry()` 會呼叫 minimized 顯示流程。
- Host 從 minimized 被還原時 emit `activated`，並重新 minimize。
- Host close 會 emit `close_requested`，由 app 轉成 quit。
- `App.start()` 建立 host、連到 `raise_window()`、啟動 taskbar entry。
- Windows App ID helper 在 `win32` 會呼叫 Win32 API，非 Windows 不做事。
- Installer `.iss` 包含 Start Menu shortcut、Desktop shortcut task、uninstaller metadata、icon。
- Installer `.iss` 不包含 taskbar pin 或 startup-on-boot 設定。

手動 QA：

1. Build PyInstaller one-folder output。
2. 執行 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`。
3. 確認 taskbar 出現 `Spotify Lyrics Widget`。
4. 隱藏 widget，確認 taskbar 圖示仍存在。
5. 點 taskbar 圖示，確認 widget 顯示並 raise。
6. 使用 tray show/hide/quit，確認 taskbar/tray 狀態一致。
7. 建 installer，安裝後確認 Start Menu shortcut 可啟動。
8. 勾選 Desktop shortcut 時確認桌面捷徑可啟動。
9. 從 Windows 設定解除安裝，確認安裝資料夾與 shortcuts 被移除。

## 風險

- 最小化 host 被點擊時可能短暫閃出空白窗，需要實測。
- Alt+Tab 可能會出現 host entry，這是 taskbar 常駐入口的副作用。
- 使用者從 taskbar 右鍵 Close window 時，應該退出 app；如果只隱藏會讓使用者困惑。
- 未簽名 installer 可能被 Windows SmartScreen 或防毒提醒。
- Inno Setup 可能不是本機已安裝工具，build script 要清楚報錯。

## 否決方案

- 直接移除 `LyricsWidget` 的 `Qt.Tool`：會改變 widget 的小工具定位，而且 widget
  被 hide 時 taskbar 仍會消失，不能滿足「app 執行中 taskbar 永遠有」。
- 建立完全 hidden 的 host：Windows 很可能不把它列進 taskbar。
- 只靠 tray icon 或通知：使用者仍可能找不到正在背景跑的 app。
- 自動 pin taskbar：Windows 不可靠，也不符合一般 installer 行為。
