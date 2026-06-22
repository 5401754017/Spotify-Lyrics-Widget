# Spotify Widget Taskbar Host 與 Installer 設計

## 背景

目前 `SpotifyLyricsWidget.exe` 比較像 tray + floating widget。歌詞視窗使用
`Qt.Tool`，這讓它像小工具一樣浮在桌面上，但 Windows 通常不會把這種工具視窗
放進 taskbar。只靠 tray icon 的問題是：使用者可能按了隱藏，之後忘記 app 還在
背景跑，也可能不知道要去系統匣找。

新的目標不是把歌詞 widget 變成一般視窗，而是讓 app 執行中時，Windows taskbar
永遠有一個入口。使用者點 taskbar 入口時，會看到一個小型控制窗；控制窗再負責
顯示、隱藏或退出 app。

## 目標

- App 執行中時，taskbar 永遠有 `Spotify Lyrics Widget` 圖示。
- 歌詞 widget 保留目前的小工具行為：frameless、always-on-top、`Qt.Tool`。
- Widget 被隱藏時，taskbar 圖示仍保留，避免使用者以為 app 消失。
- 點 taskbar entry 時，顯示小型控制窗。
- 小型控制窗可依 widget 狀態切換 `Show Widget` / `Hide Widget`，並提供 `Quit`。
- Tray icon 保留現有功能，仍可切換 widget、退出 app。
- Installer 建立 Start Menu shortcut，並提供 Desktop shortcut 選項。
- Installer 寫入正常解除安裝資訊，讓使用者能從 Windows 設定解除安裝。

## 非目標

- 不自動 pin 到 taskbar。Windows 不鼓勵 app/installer 強制釘選。
- 不把歌詞 widget 改成一般標題列視窗。
- 不做開機自啟動。
- 第一版不做 MSIX、code signing 或 Microsoft Store 發佈。
- 第一版不改 `%APPDATA%/spotify-lyrics-widget/` 的 config/log 位置。

## Taskbar Host / Control Window

新增一個同一個 process 內的 `TaskbarHostWindow`。它是一個正常 top-level window，
不使用 `Qt.Tool`，用途是讓 Windows taskbar 有穩定入口，並作為小型控制窗。

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
    +-- 啟動時 showMinimized()
    +-- taskbar 常駐入口
    +-- 被還原時顯示小型控制窗
    +-- Show/Hide Widget
    +-- Quit
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
-> host 被 Windows 還原
-> 顯示小型控制窗
-> 控制窗顯示 widget 狀態

控制窗按 Show Widget
-> App.raise_window()
-> 控制窗按鈕改成 Hide Widget

控制窗按 Hide Widget
-> widget.hide()
-> 控制窗按鈕改成 Show Widget

控制窗按 Quit
-> QApplication.quit()

控制窗按 X / taskbar Close window
-> host showMinimized()
-> app 繼續跑，taskbar entry 保留
```

這個 host 不能完全 hidden，否則 Windows 可能不會在 taskbar 顯示它。啟動時採用
`showMinimized()`，讓它存在於 taskbar；使用者點 taskbar 時還原的是有內容的小型
控制窗，不再嘗試用空白 host 視窗假裝自己不存在。

小型控制窗第一版只放 app 名稱、widget 狀態、`Show Widget` / `Hide Widget` 和
`Quit`。不加入設定、size preset 或其他功能；widget 自己原本的 hide/close 控制保留，
tray icon 原本的 show/hide/quit 行為也保留。

## 方案 A 實測結果

方案 A 已實作並在 Windows 上手動 QA。結果：

- 成功：app 執行中 taskbar entry 存在。
- 成功：tray icon 仍存在。
- 成功：widget 隱藏後 taskbar entry 仍存在。
- 成功：點 taskbar entry 能叫回 widget。
- 失敗：點 taskbar entry 時明顯閃出空白 host window。

因此方案 A 功能上可行，但 UX 不合格。後續採用方案 B：小型控制窗 host。

## 備選方案與切換條件

第一輪 implementation plan 已實作方案 A，並因空白窗閃爍而停止。第二輪
implementation plan 實作方案 B，不再混入 installer 或 shortcut 變更。

| 方案 | 行為 | 使用條件 |
| --- | --- | --- |
| A. 最小化 taskbar host | Host 啟動後 `showMinimized()`，點 taskbar 時叫回 widget，再重新最小化。 | 已實作並實測失敗：點 taskbar 時明顯閃出空白窗。 |
| B. 小型控制窗 host | 點 taskbar 時開一個小控制窗，提供 `Show Widget` / `Hide Widget`、`Quit`，widget 仍是浮動小工具。 | 目前定版方案。 |

方案 B 若仍有 taskbar entry 不穩或控制窗行為困惑，再停止並記錄手動 QA 證據。

## Windows App ID

Windows taskbar 的 icon、分組、shortcut 關聯常依賴 AppUserModelID。啟動時應在建立
Qt 視窗前設定固定 ID：

```text
SpotifyLyricsWidget.Desktop
```

這是產品層級的穩定 ID，發布後所有使用者都使用同一個值。不要包含個人名稱、
本機路徑或每台機器不同的值，否則 shortcut、taskbar 分組和 app 本體可能對不起來。
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
- `TaskbarHostWindow.set_widget_visible(True)` 會顯示 `Visible` 與 `Hide Widget`。
- `TaskbarHostWindow.set_widget_visible(False)` 會顯示 `Hidden` 與 `Show Widget`。
- 控制窗 toggle button 會 emit `toggle_widget_requested`。
- 控制窗 quit button 會 emit `quit_requested`。
- Host close 會回到 minimized，不退出 app。
- `App.start()` 建立 host、啟動 taskbar entry，並同步 widget visible 狀態。
- `App.raise_window()` 和 `_toggle_widget()` 會同步控制窗按鈕狀態。
- Windows App ID helper 在 `win32` 會呼叫 Win32 API，非 Windows 不做事。
- Installer `.iss` 包含 Start Menu shortcut、Desktop shortcut task、uninstaller metadata、icon。
- Installer `.iss` 不包含 taskbar pin 或 startup-on-boot 設定。

手動 QA：

1. Build PyInstaller one-folder output。
2. 執行 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`。
3. 確認 taskbar 出現 `Spotify Lyrics Widget`。
4. 隱藏 widget，確認 taskbar 圖示仍存在。
5. 點 taskbar 圖示，確認出現小型控制窗，而不是空白窗。
6. 控制窗按 `Hide Widget`，確認 widget 隱藏，按鈕改成 `Show Widget`。
7. 控制窗按 `Show Widget`，確認 widget 顯示並 raise，按鈕改成 `Hide Widget`。
8. 使用 tray show/hide/quit，確認 taskbar/tray/control window 狀態一致。
9. 控制窗按 X，確認控制窗回到 taskbar，app 繼續跑。
10. 控制窗按 `Quit`，確認 tray icon 和 taskbar entry 都消失。
11. 建 installer，安裝後確認 Start Menu shortcut 可啟動。
12. 勾選 Desktop shortcut 時確認桌面捷徑可啟動。
13. 從 Windows 設定解除安裝，確認安裝資料夾與 shortcuts 被移除。

## 風險

- 控制窗按 X / taskbar Close window 會回到 minimized，不退出 app；退出必須用 `Quit` 或 tray Quit。
- Alt+Tab 可能會出現 host entry，這是 taskbar 常駐入口的副作用。
- 控制窗是正常視窗，使用者會多看到一個小視窗；這是避免空白窗閃爍的取捨。
- 未簽名 installer 可能被 Windows SmartScreen 或防毒提醒。
- Inno Setup 可能不是本機已安裝工具，build script 要清楚報錯。

## 否決方案

- 直接移除 `LyricsWidget` 的 `Qt.Tool`：會改變 widget 的小工具定位，而且 widget
  被 hide 時 taskbar 仍會消失，不能滿足「app 執行中 taskbar 永遠有」。
- 建立完全 hidden 的 host：Windows 很可能不把它列進 taskbar。
- 只靠 tray icon 或通知：使用者仍可能找不到正在背景跑的 app。
- 自動 pin taskbar：Windows 不可靠，也不符合一般 installer 行為。
