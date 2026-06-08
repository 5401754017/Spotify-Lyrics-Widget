# Spotify Lyrics Widget

Windows 桌面 Spotify 歌詞小工具。

## 使用方式

1. 下載 portable zip。
2. 解壓縮整個資料夾。
3. 執行 `SpotifyLyricsWidget.exe`。
4. 第一次啟動時，依照「Spotify 初始設定」視窗完成 Spotify 設定。

## 第一次 Spotify 設定

這個工具需要你自己的 Spotify App Client ID。

1. 在設定視窗按「開啟 Dashboard」。
2. 到 Spotify Developer Dashboard 建立一個 app。
3. 在 Spotify app 設定裡加入 Redirect URI：

```text
http://127.0.0.1:8888/callback
```

4. 複製 Spotify app 的 Client ID。
5. 回到工具，把 Client ID 貼上。
6. 按「連接 Spotify」，瀏覽器會開啟 Spotify 登入授權。

## 資料位置

設定和 log 會放在：

```text
%APPDATA%/spotify-lyrics-widget
```

更新新版時，可以替換 app 資料夾；原本的 token 和設定會保留。

## 常見問題

如果 Spotify 顯示 invalid redirect URI，請確認 Spotify Dashboard 裡的 Redirect URI 完全等於：

```text
http://127.0.0.1:8888/callback
```

如果 app 沒有反應，可以查看 log：

```text
%APPDATA%/spotify-lyrics-widget/widget.log
```
