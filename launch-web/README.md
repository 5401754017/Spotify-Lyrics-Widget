# Launch Web — 產品官網

Spotify Lyrics Widget 的產品介紹頁，繁中 + 英文雙語，靜態網站，部署在 GitHub Pages。

線上網址：<https://5401754017.github.io/Spotify-Lyrics-Widget/>

## 結構

```
launch-web/
├─ site/
│  ├─ template.html      版型（唯一改結構/樣式的地方，含 {{佔位符}}）
│  ├─ build.py           產生器 + 所有可變設定（單一來源）
│  ├─ i18n/
│  │  ├─ zh-Hant.json    繁中所有文字
│  │  └─ en.json         英文所有文字
│  ├─ index.html         語言路由（產生檔）
│  ├─ zh-Hant/index.html 繁中頁（產生檔）
│  ├─ en/index.html      英文頁（產生檔）
│  └─ assets/            app-icon、favicon、og.png
├─ scripts/make_og.py    產生 1200×630 社群分享圖 og.png
└─ design_src/           原始 Claude Design 匯出檔（僅參考）
```

`index.html` / `zh-Hant/` / `en/` 都是**產生檔，不要手改**。改 `template.html` 或 `i18n/*.json` 後跑 build。

## 開發流程

```bash
python site/build.py          # 產生三個頁面
```

改完 commit + push，GitHub Actions 會自動重新部署（只在 `launch-web/site/**` 有變動時觸發）。

## 常見修改

### 改文字

編輯 `site/i18n/zh-Hant.json` 或 `en.json`，跑 build。兩份的 key 必須一致，缺 key build 會報錯。

### 加語言（例如日文 ja）

1. 複製 `site/i18n/en.json` → `site/i18n/ja.json`，翻譯所有值。
2. `site/build.py` 的 `LANGS` 加 `"ja"`。
3. 跑 build。版型、切換器、hreflang 會自動有。

### 發新版

改 `site/build.py` 最上面一行：

```python
VERSION = "v3.2.1"   # ← 改成新版
```

版本 badge 和三顆下載按鈕（nav / hero / 下載區）的連結會一起更新。

### 改 GitHub username 或 repo 名

改 `site/build.py`：

```python
USER = "5401754017"            # ← 新 username
REPO_NAME = "Spotify-Lyrics-Widget"
```

所有 GitHub 連結（nav / footer / 下載區）、OG 圖絕對網址、下載連結都會跟著更新。跑 build。

**注意**：改 username 除了上面這步，還要處理 repo 外的東西：

1. `git remote set-url origin https://github.com/<新username>/Spotify-Lyrics-Widget.git`
   （GitHub 會自動把舊 username 轉址到新的，但還是更新比較乾淨。）
2. Pages 網址會自動變成 `<新username>.github.io/Spotify-Lyrics-Widget/`，Actions 不用改。
3. build → commit → push，讓線上的 OG 圖和連結指到新網址。

### 換 OG 分享圖

改 `scripts/make_og.py`，跑：

```bash
python scripts/make_og.py     # 重新產生 site/assets/og.png
```

需要 Pillow（`pip install pillow`）。用的是 Windows 內建字型（微軟正黑體 / Segoe UI）。

## 部署

- Workflow：`.github/workflows/deploy-pages.yml`
- 觸發：push 到 `master` 且 `launch-web/site/**` 有變動；也可到 Actions 分頁手動 Run。
- 直接發佈已 build 好的靜態檔，CI 不跑 Python。
