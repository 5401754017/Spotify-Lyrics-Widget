# Spotify Widget Taskbar Host 與 Installer 設計

## 背景

目前 `SpotifyLyricsWidget.exe` 比較像 tray + floating widget。歌詞視窗使用
`Qt.Tool`，這讓它像小工具一樣浮在桌面上，但 Windows 通常不會把這種工具視窗
放進 taskbar。只靠 tray icon 的問題是：使用者可能按了隱藏，之後忘記 app 還在
背景跑，也可能不知道要去系統匣找。

新的目標不是把歌詞 widget 變成一般視窗，而是建立一個 Windows 能辨識的
controller。controller 負責 taskbar entry 與小型控制窗；widget 仍然是浮動小工具，
但它的 Run / Close 與 Show / Hide 都由 controller、widget 自身控制、tray icon 共同
同步狀態。

## 目標

- Controller 執行中時，taskbar 永遠有 `Spotify Lyrics Widget` 圖示。
- 歌詞 widget 保留目前的小工具行為：frameless、always-on-top、`Qt.Tool`。
- Widget 被隱藏時，taskbar 圖示仍保留，避免使用者以為 controller 消失。
- 點 taskbar entry 時，顯示小型控制窗。
- 小型控制窗顯示 `Widget: Stopped/Running` 與 `Widget: Visible/Hidden`。
- 小型控制窗提供 `Widget Disabled` / `Show Widget` / `Hide Widget` 與 `Run Widget` / `Close Widget`。
- Tray icon 綁定 widget：widget running 時顯示 tray，widget stopped 時 tray 消失。
- Tray icon 點擊只切換 widget visible/hidden；tray menu 的關閉動作是 `Close Widget`。
- Controller 視窗按 X 會先 close widget，再關閉 controller/taskbar entry。
- Installer 建立 Start Menu shortcut，並提供 Desktop shortcut 選項。
- Installer 寫入正常解除安裝資訊，讓使用者能從 Windows 設定解除安裝。

## 非目標

- 不自動 pin 到 taskbar。Windows 不鼓勵 app/installer 強制釘選。
- 不把歌詞 widget 改成一般標題列視窗。
- 不做開機自啟動。
- 第一版不做 MSIX、code signing 或 Microsoft Store 發佈。
- 第一版不改 `%APPDATA%/spotify-lyrics-widget/` 的 config/log 位置。

## Taskbar Host / Controller Window

新增一個同一個 process 內的 `TaskbarHostWindow`。它是一個正常 top-level window，
不使用 `Qt.Tool`，用途是讓 Windows taskbar 有穩定入口，並作為 controller 小窗。

```text
SpotifyLyricsWidget.exe
+-- Controller
|   +-- TaskbarHostWindow
|   +-- 一般 top-level window
|   +-- taskbar 常駐入口
|   +-- Run Widget / Close Widget
|   +-- Show Widget / Hide Widget
|
+-- Widget session
|   +-- LyricsWidget
|   |   +-- Qt.Tool
|   |   +-- floating / frameless / always-on-top
|   |   +-- Visible / Hidden
|   +-- SpotifyWorker
|   +-- LyricsWorker
|
+-- TrayIcon
    +-- 只在 Widget: Running 時存在
    +-- click: Show/Hide Widget
    +-- menu: Close Widget
```

Controller UI 定版：

```text
Widget: Stopped/Running
Widget: Visible/Hidden
[Widget Disabled]/[Hide Widget]/[Show Widget]    [Run Widget]/[Close Widget]
```

狀態表：

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

Lifecycle 行為：

```text
啟動 controller
-> TaskbarHostWindow showMinimized()
-> taskbar 出現 Spotify Lyrics Widget
-> widget 初始 Stopped / Hidden
-> tray 不顯示

控制窗按 Run Widget
-> 建立 widget session
-> OAuth / worker / tray 啟動
-> widget 顯示
-> controller 狀態變成 Running + Visible

控制窗按 Hide Widget
-> widget.hide()
-> controller 狀態變成 Running + Hidden
-> tray 保留

控制窗按 Show Widget
-> widget showNormal / raise / activate
-> controller 狀態變成 Running + Visible
-> tray 保留

widget hide 按鈕或 tray icon 點擊
-> 只切換 Visible / Hidden
-> controller 狀態同步

控制窗按 Close Widget / widget close / tray menu Close Widget
-> 停止 widget session
-> widget hidden / workers stopped / tray hidden
-> controller 保留在 taskbar
-> controller 狀態變成 Stopped + Hidden

控制窗按 X / taskbar Close window
-> 若 widget Running，先 Close Widget
-> 關閉 controller window
-> taskbar entry 消失
```

這個 host 不能完全 hidden，否則 Windows 可能不會在 taskbar 顯示它。啟動時採用
`showMinimized()`，讓它存在於 taskbar；使用者點 taskbar 時還原的是有內容的小型
controller，不再嘗試用空白 host 視窗假裝自己不存在。

小型 controller 第一版只放 app 名稱、兩行 widget 狀態、Show/Hide/Disabled 按鈕與
Run/Close 按鈕。不加入設定、size preset 或其他功能；widget 自己原本的 hide/close
控制保留，tray icon 的職責改成跟隨 widget running 狀態。

## 方案 A 實測結果

方案 A 已實作並在 Windows 上手動 QA。結果：

- 成功：controller 執行中 taskbar entry 存在。
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
| B. Controller 小窗 host | 點 taskbar 時開一個小 controller，提供 widget Run/Close 與 Show/Hide，widget 仍是浮動小工具。 | 目前定版方案。 |

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
- `TaskbarHostWindow.set_widget_state(False, False)` 會顯示 `Stopped`、`Hidden`、disabled `Widget Disabled`、`Run Widget`。
- `TaskbarHostWindow.set_widget_state(True, True)` 會顯示 `Running`、`Visible`、`Hide Widget`、`Close Widget`。
- `TaskbarHostWindow.set_widget_state(True, False)` 會顯示 `Running`、`Hidden`、`Show Widget`、`Close Widget`。
- 控制窗 left button 會依狀態 emit `show_widget_requested` 或 `hide_widget_requested`。
- 控制窗 stopped 狀態下 left button disabled，不 emit show/hide。
- 控制窗 right button 會依狀態 emit `run_widget_requested` 或 `close_widget_requested`。
- 控制窗 close event 會 emit `controller_close_requested` 並接受 close。
- `App.start()` 只啟動 controller/taskbar entry，widget 初始 Stopped，tray 不顯示。
- `App._run_widget()` 建立 widget session、worker、tray，並同步 Running + Visible。
- `App._hide_widget()` / `App._show_widget()` 只切換 Visible / Hidden，並同步 controller。
- `App._close_widget()` 停止 workers、隱藏 tray、清掉 widget session，controller 保留。
- Widget close、tray menu `Close Widget`、controller `Close Widget` 都走同一個 `_close_widget()`。
- Controller X 走 `_close_controller()`，先 close widget，再關閉 controller/taskbar entry。
- Windows App ID helper 在 `win32` 會呼叫 Win32 API，非 Windows 不做事。
- Installer `.iss` 包含 Start Menu shortcut、Desktop shortcut task、uninstaller metadata、icon。
- Installer `.iss` 不包含 taskbar pin 或 startup-on-boot 設定。

手動 QA：

1. Build PyInstaller one-folder output。
2. 執行 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`。
3. 確認 taskbar 出現 `Spotify Lyrics Widget`，tray icon 尚未出現。
4. 點 taskbar 圖示，確認出現小型 controller，而不是空白窗。
5. 確認 controller 顯示 `Widget: Stopped`、`Widget: Hidden`、disabled `Widget Disabled`、`Run Widget`。
6. 按 `Run Widget`，確認 widget 顯示、tray icon 出現，controller 變成 Running + Visible。
7. 按 `Hide Widget`，確認 widget 隱藏，controller 變成 Running + Hidden，tray icon 保留。
8. 按 `Show Widget`，確認 widget 顯示並 raise，controller 變成 Running + Visible。
9. 用 widget hide 按鈕與 tray icon click 各切一次，確認 controller 狀態同步。
10. 用 controller `Close Widget`，確認 widget 隱藏、tray icon 消失、taskbar/controller 保留，狀態變成 Stopped + Hidden。
11. 再按 `Run Widget`，確認 widget session 可以重新啟動。
12. 用 widget close，確認結果等同 `Close Widget`：widget/tray 關閉，controller 保留。
13. 用 tray menu `Close Widget`，確認結果等同 `Close Widget`：widget/tray 關閉，controller 保留。
14. Widget Running 時按 controller X，確認 widget/tray 關閉，taskbar/controller 消失。
15. Widget Stopped 時按 controller X，確認 taskbar/controller 消失。
16. 建 installer，安裝後確認 Start Menu shortcut 可啟動。
17. 勾選 Desktop shortcut 時確認桌面捷徑可啟動。
18. 從 Windows 設定解除安裝，確認安裝資料夾與 shortcuts 被移除。

## 風險

- Controller X 不再只是 minimize；它會 close widget 並關閉 controller/taskbar entry。
- Widget close / tray menu Close Widget 不會關閉 controller；它們只停止 widget session。
- Alt+Tab 可能會出現 host entry，這是 taskbar 常駐入口的副作用。
- 控制窗是正常視窗，使用者會多看到一個小視窗；這是避免空白窗閃爍的取捨。
- 未簽名 installer 可能被 Windows SmartScreen 或防毒提醒。
- Inno Setup 可能不是本機已安裝工具，build script 要清楚報錯。

## 否決方案

- 直接移除 `LyricsWidget` 的 `Qt.Tool`：會改變 widget 的小工具定位，而且 widget
  被 hide 時 taskbar 仍會消失，不能滿足「controller 執行中 taskbar 永遠有」。
- 建立完全 hidden 的 host：Windows 很可能不把它列進 taskbar。
- 只靠 tray icon 或通知：使用者仍可能找不到正在背景跑的 app。
- 自動 pin taskbar：Windows 不可靠，也不符合一般 installer 行為。
