# Spotify 歌詞懸浮視窗 — 開發交接文件

最後更新：2026年5月

---

## 為什麼做這個

平常聽 Spotify 想看歌詞一定要打開 App 才能看，體驗很麻煩。想做一個常駐在桌面的懸浮小視窗，自動顯示當前播放歌曲的歌詞，音樂播到哪行只顯示哪行，減小佔據螢幕畫面，不用切換 App。

這是一個自用工具，不需要市場驗證。開發週期短、失敗成本低，做完可以放 GitHub 當履歷作品。

---

## 目標效果

- 任意位置有一個小懸浮視窗，永遠在最上層，可以自由拖曳
- 顯示當前播放的歌名與歌手
- 歌詞逐行顯示，播放到哪行就顯示那行
- 風格走 Spotify 黑綠色調
- 無邊框、乾淨、不干擾其他視窗

---

## 技術選型

**語言：** Python

**GUI：** PyQt6
- Windows 上做懸浮視窗最適合
- 支援無邊框視窗、永遠在最上層、透明背景
- 打包成 .exe 用 PyInstaller 一行搞定

**API：**
- Spotify Web API — `Get Currently Playing Track`，每秒 poll 一次，拿歌名、歌手、播放進度（毫秒）
- lrclib.net — 開放 API，免費，提供 LRC 格式歌詞（每行有時間戳），用來做同步高亮
- Genius API — fallback 用，當 lrclib 查不到時顯示純文字歌詞（無同步）

---

## 核心流程

1. 啟動時引導使用者完成 Spotify OAuth 授權
2. 每秒 poll Spotify API，拿到：歌名、歌手、播放進度（ms）、是否在播放
3. 歌曲變換時，去 lrclib.net 查 LRC 歌詞
4. 解析 LRC 時間戳，建立「時間 → 歌詞行」的對照表
5. 每秒比對當前播放進度，找到對應行，高亮顯示
6. 若 lrclib 查不到，fallback 去 Genius 查純文字歌詞，靜態顯示

---

## 需要處理的細節

- **換歌偵測：** track ID 變了就清掉舊 LRC，重新查新歌
- **暫停處理：** Spotify API 回傳 is_playing = false 時，視窗保持顯示但停止滾動
- **Rate limit：** Spotify API poll 頻率每秒一次即可，不要更頻繁
- **lrclib 查不到：** fallback 到 Genius，靜態顯示整段歌詞，不做同步
- **視窗行為：** 可拖曳移動位置，可最小化，不影響其他視窗的點擊

---

## 開發順序建議

1. 先跑通 Spotify OAuth + 抓當前播放歌曲（CLI 印出來確認）
2. 接 lrclib.net，確認可以查到 LRC 並正確解析時間戳
3. 做最簡單的 PyQt6 視窗，先只顯示歌名
4. 把歌詞塞進視窗，做逐行顯示
5. 調整視覺風格（黑綠色、字體、無邊框）
6. 加入 fallback 邏輯（lrclib 查無 → Genius）
7. PyInstaller 打包成 .exe

---

## 不在這次範圍內

- 歌詞翻譯功能（之後可擴充）
- Mac / Linux 支援（目前只做 Windows）
- 商業化（純自用 + 開源）
