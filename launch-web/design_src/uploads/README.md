# Spotify Lyrics Widget

Windows 桌面 Spotify 歌詞小工具。

## 使用方式

1. 下載 `SpotifyLyricsWidgetSetup.exe`。
2. 執行安裝程式，選擇語言並完成安裝。
3. 從 Start Menu 或桌面捷徑開啟 `SpotifyLyricsWidget.exe`。
4. 第一次啟動時，依照「Spotify 初始設定 / Spotify Setup」視窗完成 Spotify 設定。

## 第一次 Spotify 設定

這個工具需要你自己的 Spotify App Client ID。

1. 在設定視窗按「開啟 Dashboard」，登入 Spotify 後按 **Create App**。
2. 填寫 App 資料：
   - **App name**：隨便取（例如 `Lyrics Widget`）
   - **App description**：隨便寫
   - **Redirect URI**：貼上下面這串，按 Add
     ```
     http://127.0.0.1:8888/callback
     ```
   - **API**：勾選 **Web API**
   - 勾選同意條款，按 **Save**
3. App 建好後，進入 app 頁面，到 **Settings** 複製 **Client ID**。
4. 回到工具，把 Client ID 貼上，按「連接 Spotify」。
5. 瀏覽器會開啟 Spotify 登入授權，按 **Agree** 同意。

## 資料位置

設定和 log 會放在：

```text
%APPDATA%/spotify-lyrics-widget
```

更新新版時，重新執行 installer；原本的 token 和設定會保留。

## 常見問題

如果 Spotify 顯示 invalid redirect URI，請確認 Spotify Dashboard 裡的 Redirect URI 完全等於：

```text
http://127.0.0.1:8888/callback
```

如果 app 沒有反應，可以查看 log：

```text
%APPDATA%/spotify-lyrics-widget/widget.log
```
