# Spotify Lyrics Widget 尺寸 Preset 設計

日期：2026-06-06
狀態：等待使用者 review

## 目標

新增固定的 widget 尺寸 preset，讓懸浮歌詞視窗可以少佔一點桌面空間，同時避免自由縮放造成 UI 變得不穩。

這不是 freeform resize，也不是純等比例縮放，而是 density preset：每個 preset 都有固定寬高、字體大小、padding、gap、歌詞行數。

目前 `420x112` 保留為最大尺寸，也是預設尺寸。較小的 preset 會逐步縮小寬度、高度、padding、gap 和歌詞字體。Mini 是最極端的精簡模式，只顯示一行歌詞，超過就用 `...` 省略。

## 不做的事

- 不做自由拖曳 resize。
- 不做連續 scale slider。
- 不做 content-driven auto-resize。
- 不改播放控制行為。
- 不改歌詞查詢、cache 或同步 timing。

## 尺寸 Preset

| Preset | 視窗尺寸 | Title font | Lyric font | 歌詞行數 | 用途 |
| --- | --- | --- | --- | --- | --- |
| Current | `420x112` | `10pt` | `16pt` | 2 | 目前 layout，最大尺寸 |
| Compact | `380x96` | `10pt` | `14pt` | 2 | 比目前小，但仍然舒適 |
| Small | `340x84` | `9pt` | `12pt` | 2 | 比較密集的日常尺寸 |
| Mini | `300x74` | `8pt` | `10pt` | 1 | 最精簡尺寸 |

如果實作後的 screenshot 顯示文字或按鈕被切到，先回來修這份 spec，再改數值。重要契約是：固定寬高、固定字體、固定歌詞行數，不產生任意中間尺寸。

## Layout 規則

每個 preset 都是一份完整 layout profile，包含：

- Widget 寬度與高度。
- Panel margins。
- Top row height。
- Title 和 lyric lane 之間的 gap。
- Lyric lane height。
- Progress bar height。
- Transport controls 的大小與位置。
- Close button 的大小與位置。
- Title 和 lyric 的 font size。
- 最大 lyric visual lines。

UI 不應該計算任意中間尺寸。程式只套用其中一個 profile，然後根據 profile 重新定位 overlay controls。

Mini 模式使用一行 lyric clamp。如果歌詞放不下，就用 `...` 省略。Current、Compact、Small 保留目前最多兩個 visual lines 的歌詞行為。

## 切換方式

在現有 tray menu 裡新增 `Size` submenu：

```text
Size
- Current
- Compact
- Small
- Mini
```

選到某個 preset 後，立即套用到 widget，並保存到 config。tray menu 裡目前選中的 preset 要顯示 checked 狀態。下次啟動時，widget 要恢復上次保存的 preset。

第一版不加 resize handle，也不加 keyboard shortcut。

## Config

新增持久化欄位 `size_preset`。

預設值：

```json
"size_preset": "current"
```

允許值：

```text
current
compact
small
mini
```

如果 config 裡是未知值，啟動時 fallback 到 `current`。但不要因為啟動 fallback 就立刻寫回 config；等使用者手動選擇有效 preset 時再保存，避免啟動時產生意外檔案寫入。

## 實作形狀

`src/widget.py` 應該定義一個小型 preset data structure，並提供一個方法套用 preset。這個方法負責更新 fixed size、margins、row heights、fonts、button sizes、control positions 和 lyric line count。

`src/lyric_clamp.py` 應該支援指定最大 visual line count。目前行為等於 `max_lines=2`；Mini 使用 `max_lines=1`。

`src/tray.py` 應該新增 size submenu，並在使用者選擇 preset 時 emit signal 或呼叫 callback。`src/main.py` 負責把 tray callback 接到 widget 和 config save。

## 測試

需要新增或更新測試：

- Config 的 `size_preset` 預設值與保存。
- Widget 套用每個 preset 後的固定寬高、font size、lyric line count。
- Mini lyric text 會 clamp 成一行並用 `...` 省略。
- Current、Compact、Small 保留兩行 lyric clamp。
- Tray menu 包含 `Size` submenu 和四個 preset。
- 選擇 preset 後會更新 widget 並保存 config。

完成前要跑 full suite。

## 版本邊界

如果在 V3 packaging 前實作，這應該是 **V2.03 UI polish**。這是使用者可見的新功能，但不改變專案方向。
