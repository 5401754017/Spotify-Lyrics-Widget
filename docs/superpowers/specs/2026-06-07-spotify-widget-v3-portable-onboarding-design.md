# Spotify Widget V3 Portable Onboarding 設計

## 目前決策

V3 的目標是讓公開使用者不用懂 Python 也能試用。發佈形式先做成免安裝的 portable zip，裡面包含可執行檔。使用者下載、解壓縮，然後執行 `SpotifyLyricsWidget.exe`。

V3 這裡說的「portable」是指不用安裝 Python、不用打指令。它不是指所有設定檔都一定要放在 exe 旁邊。設定和 log 先保留在 `%APPDATA%/spotify-lyrics-widget/`，這樣使用者之後替換新版 app 資料夾時，原本的 token 和偏好設定不會被洗掉。

## Spotify 公開使用限制

公開發佈時，app 不應該依賴開發者自己的 Spotify `client_id` 給所有人共用。

Spotify Development Mode 有限制，而且使用者需要被加入 allowlist。Extended quota mode 才是大量公開使用的正式路線，但 Spotify 目前的申請條件對這個專案來說不實際。因此 V3 先做 first-run onboarding dialog，引導每個使用者建立自己的 Spotify app，然後貼上自己的 `client_id`。

相關官方文件：

- Spotify apps: `https://developer.spotify.com/documentation/web-api/concepts/apps`
- Quota modes: `https://developer.spotify.com/documentation/web-api/concepts/quota-modes`
- Redirect URI rules: `https://developer.spotify.com/documentation/web-api/concepts/redirect_uri`

## 使用者體驗

第一次啟動時，應該顯示真正的 PyQt 設定視窗，取代目前單純的文字輸入框。

設定視窗要簡單、直接、以操作為主：

```text
+------------------------------------------------+
| Spotify 初始設定                              |
+------------------------------------------------+
| 1. 開啟 Spotify Developer Dashboard            |
|    [開啟 Dashboard]                            |
|                                                |
| 2. 把這個 Redirect URI 加到 Spotify app        |
|    http://127.0.0.1:8888/callback              |
|    [複製 Redirect URI]                         |
|                                                |
| 3. 貼上你的 Client ID                          |
|    [____________________________]              |
|                                                |
|              [取消] [連接 Spotify]             |
+------------------------------------------------+
```

這個視窗不負責自動建立 Spotify 帳號或 Spotify app。它只提供必要輔助：按鈕開啟 Dashboard、按鈕複製 redirect URI、檢查 Client ID 不是空白、存進 config，然後接到現有 OAuth 流程。

文案要假設使用者不是工程師，但不要把很長的教學塞進 app 裡。release zip 可以附一份短版 `README.md` 當備用說明。

## 架構

新增一個小型 first-run setup dialog module，保留現有 auth flow。

預計元件：

- `src/onboarding.py`：PyQt 初始設定視窗。
- `src/main.py`：把目前 `QInputDialog.getText(...)` 那段改成 onboarding dialog。
- `src/config.py`：保留目前 `%APPDATA%` 的 config 行為。
- `README.md`：短版備用教學，release zip 會附上。
- 打包檔案：PyInstaller spec 和 build script，用來產生 one-folder portable zip。

不需要新增 auth protocol。app 目前已經使用 PKCE 和 `http://127.0.0.1:8888/callback`，符合 Spotify 對 loopback redirect 的建議。

## 資料流程

```text
使用者打開 exe
  |
從 %APPDATA%/spotify-lyrics-widget/config.json 載入 config
  |
缺少 client_id？
  |
是 -> 顯示 onboarding dialog
  |
使用者開啟 dashboard、複製 redirect URI、貼上 Client ID
  |
dialog 透過 Config.save() 儲存 client_id
  |
進入現有 OAuth flow
  |
token 和偏好設定留在 %APPDATA%
```

如果 `client_id` 已經存在，啟動時就跳過 onboarding，行為和目前 app 一樣。

## 打包

先使用 PyInstaller 的 one-folder 輸出。這對 PyQt6 來說比單一 exe 穩，也比較容易在 asset 或 Qt plugin 缺漏時 debug。

Release 結構：

```text
SpotifyLyricsWidget-v3-portable/
  SpotifyLyricsWidget.exe
  _internal/
  README.md
```

Dashboard 按鈕應該開啟 `https://developer.spotify.com/dashboard`。

Build 必須包含：

- PyQt6 runtime 和 Qt plugins。
- `assets/fonts/NotoSansTC-VF.ttf`。
- 目前 `src` 底下的 source package。
- 一般啟動時不要顯示 console 視窗。

產生出來的 `dist/` 和 release zip 是 build artifacts，不應該進 git。

## 測試

實作前先補聚焦測試：

- 缺少 `client_id` 時，開 onboarding，而不是 `QInputDialog`。
- onboarding 按下接受後，會儲存 Client ID 並繼續啟動。
- onboarding 按取消後，會退出，不啟動 workers。
- 已有 `client_id` 時，跳過 onboarding。
- onboarding 裡顯示的 Redirect URI 要和 `src.auth.REDIRECT_URI` 一致。
- 打包指令能產生 one-folder build。

最終 portable build 的手動 smoke test：

1. 建立 portable folder。
2. 從乾淨 config directory 執行 exe。
3. 確認 onboarding 有出現。
4. 確認「開啟 Dashboard」會開啟 Spotify dashboard。
5. 確認「複製 Redirect URI」會複製 `http://127.0.0.1:8888/callback`。
6. 貼上 Client ID 並完成 OAuth。
7. 確認 tray、歌詞、尺寸選單、logging、乾淨關閉都還能運作。
8. 用重新 build 的 app folder 取代舊 app folder，確認 config 仍然保留。

## 暫緩項目

- 完整 data-portable mode，也就是 config/log 跟 exe 放在一起。
- 單一檔案 PyInstaller executable。
- Code signing。
- Installer/MSIX。
- 專案自己持有、且已通過 extended quota 的 Spotify Client ID。
- 有截圖、多頁流程的完整 wizard。

這些先刻意暫緩，因為第一個公開使用門檻是不用 Python 啟動，以及清楚引導使用者完成 Spotify 設定。
