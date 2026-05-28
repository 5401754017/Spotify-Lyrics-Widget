# V1.5 Handoff to Codex (2026-05-28)

**Branch:** `feature/v1-4-netease-fallback`（V1.5 疊在 V1.4 branch 上，用戶已同意）
**Plan:** `docs/superpowers/plans/2026-05-28-spotify-lyrics-widget-v1-5-logging-hygiene.md` — 已 commit、完整、有實作碼跟測試碼，照著做就好。

---

## 進度

| Task | Commit | 狀態 |
|------|--------|------|
| 0 — Plan + roadmap + V1.4 verification note | `bda7910` | ✅ |
| 1 — Worker `run()` 三個出口加 log | `ee239f2` | ✅ |
| 2 — LRCLIB fetch `/get` `/search` 決策點加 log | `38cfea7` | ✅ |
| 3 — `App._ensure_auth` 預刷新警告 | `c80ccc8` | ✅ |
| **4 — `spotify_worker._poll_once` 網路例外加 log** | — | **下一個** |
| 5 — 全套 + 文件收尾 | — | 最後 |

最後 commit: `c80ccc8`，工作目錄乾淨。

---

## 你要做的：Task 4 → Task 5

兩個都照 plan 跑就好，plan 的步驟拆得很細（每步都是 2~5 分鐘）：

- **Task 4**：在 `src/spotify_worker.py` 的 `_poll_once` 那個 `except (httpx.ConnectError, httpx.TimeoutException)` 分支前面加一行 `logging.warning(...)`，含例外類別 + 訊息。新增一個 caplog 測試到 `tests/test_spotify_worker.py`。Commit。
- **Task 5**：跑全套測試 → 更新 roadmap 把 V1.5 commit hash 補進 "Current state (done)"（hashes: `ee239f2`, `38cfea7`, `c80ccc8`, 加你 Task 4 的）→ commit 文件。

Task 5 step 2 那個「實機驗收」（重啟 widget 播 3 種歌看 log）**由用戶自己操作**，你不用碰 widget process。

---

## 環境注意事項（一定要看）

1. **pytest 跑法**：用戶機器上預設的 `pytest-of-crayo` 暫存夾權限壞掉，直接打 `pytest` 會 8 個 error。必須帶旗標：
   ```
   python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q <args>
   ```

2. **`tests/test_main.py` 在這台機器今天會炸**：PyQt6 6.11.0 環境問題，exit code `-1073740791` (STATUS_STACK_BUFFER_OVERRUN)。**已驗證跟 V1.5 無關**（checkout V1.4 head `2b26a26`、不帶任何 V1.5 改動，照炸）。Task 3 的新測試獨立跑是 PASS 的：
   ```
   python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp tests/test_main.py::test_ensure_auth_warns_when_pre_refresh_fails_then_falls_through -v
   ```
   **不要去追這個 crash**——不是 V1.5 範圍。Task 5 全套測試時遇到 test_main.py 出狀況，照樣繼續，把這件事寫進 commit message 或 roadmap 註記即可。其他 13 個檔案（141 個測試）今天都跑得綠。

3. **不要動以下既定設計**（這些是用戶之前跟 Claude × Codex 共識定下來的）：
   - LRCLIB 不可用時不試網易 — V1.4 故意這樣設計
   - V1.5 只加 log、零行為變更
   - 用戶 CLAUDE.md 規定：不准 `except: pass`、不准在 commit 訊息加 emoji
   - Commit 結尾要加 `Co-Authored-By: <你的名字> <你的 email>`（依你慣例）

4. **網易測試備用對象**（如果 Task 5 要做 smoke test，這些歌 V1.4 verification 證實 LRCLIB 沒有、網易有）：等待你那天 / 記得呼吸 / 小宇宙 / 夏夕夏景 / 你睡了之後 / Dizzy Me（都是呂允）。

---

## 不在 V1.5 範圍、別碰

- 「LRCLIB 不可用時要不要也試網易」這個設計變更 — 用戶要走 codex 共識另開（見 `memory/codex-consensus-and-validate-before-adopting.md`）
- 「重感情的廢物」暫停時 lyric label 黑掉的 UI bug — 用戶說等下次觸發再追
- UI 側 slot 的 log（`_on_lyrics_ready` / `_on_no_lyrics` / `_on_lyrics_unavailable`）— 用戶當下沒同意納入 V1.5

---

## 完成定義

- Task 4 commit 上 branch
- Task 5 跑全套（記得排除 test_main.py 的環境 crash，其他都該綠）
- Roadmap 更新並 commit
- 回報給用戶最後 commit hash 及 V1.5 完成
