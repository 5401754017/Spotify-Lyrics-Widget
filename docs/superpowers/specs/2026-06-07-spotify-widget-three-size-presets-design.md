# Spotify Lyrics Widget 三段尺寸 Preset 設計

日期：2026-06-07
狀態：已實作，等待使用者視覺 review

## 目標

把 V2.03 的四段尺寸 preset 收斂成三段：Small / Medium / Large。

V2.03 已完成 Current / Compact / Small / Mini，但實機觀察後，四段太細，而且 Compact 與 Small 的差距不像同一套均勻階梯。新的版本保留最小與最大兩端，再把中間兩段合成一個更自然的 Medium。

這是 V2.04 UI polish：不改 Spotify polling、歌詞查詢、playback control、tray 行為，只改尺寸 preset 的命名與數值。

## 不做的事

- 不做自由拖曳 resize。
- 不做 scale slider。
- 不做 content-driven auto-resize。
- 不新增第四個 hidden/custom preset。
- 不改歌詞最多兩個 visual lines 的現況。
- 不改 tray 左鍵 toggle widget、右鍵 Size/Quit 的現況。

## 尺寸 Preset

| 新 Preset | 來源 | 視窗尺寸 | Title font | Lyric font | 歌詞行數 | 用途 |
| --- | --- | --- | --- | --- | --- | --- |
| Small | 原 Mini | `300x74` | `8pt` | `10pt` | 2 | 最省空間 |
| Medium | 原 Compact / Small 合併 | `360x90` | `9pt` | `13pt` | 2 | 預設之外的日常小尺寸 |
| Large | 原 Current | `420x112` | `10pt` | `16pt` | 2 | 最大尺寸，也是預設 |

選擇 `300 / 360 / 420` 是為了讓寬度間距固定為 `60px`，比 V2.03 的 `300 / 340 / 380 / 420` 更清楚。高度用 `74 / 90 / 112`，讓 Medium 真正落在 Small 與 Large 中間，但保留 Large 的舒適感。

## Layout Profile

每個 preset 仍是一份完整 layout profile，不用比例推算中間狀態。

### 垂直配置

```text
height = top padding + top row + gap 1 + lyric lane + gap 2 + progress + bottom padding
```

| Preset | Window height | Top padding | Top row | Gap 1 | Lyric lane | Gap 2 | Progress | Bottom padding |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Small | `74` | `6` | `18` | `2` | `41` | `2` | `1` | `4` |
| Medium | `90` | `8` | `21` | `4` | `48` | `3` | `1` | `5` |
| Large | `112` | `12` | `24` | `5` | `56` | `5` | `2` | `8` |

### Top Row 水平配置

```text
| left margin | title slot | title/control gap | controls slot | controls/close gap | close slot | right margin |
```

| Preset | Window width | Left | Title slot | Title/control gap | Controls slot | Controls/close gap | Close slot | Right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Small | `300` | `10` | `198` | `8` | `56` | `6` | `18` | `6` |
| Medium | `360` | `13` | `237` | `11` | `62` | `9` | `19` | `9` |
| Large | `420` | `16` | `282` | `14` | `66` | `12` | `20` | `10` |

Controls 和 close slot 仍固定保留，title 只吃剩餘寬度。Hover 顯示 controls 時，title label 不能跳動。

### Button / Close 尺寸

| Preset | Button size | Controls spacing | Controls height | Close size | Close font |
| --- | --- | --- | --- | --- | --- |
| Small | `16x22` | `4` | `22` | `18x18` | `12px` |
| Medium | `17x23` | `5` | `23` | `19x19` | `13px` |
| Large | `18x24` | `6` | `24` | `20x20` | `14px` |

## Tray Menu

Tray right-click menu 保持簡化版：

```text
Size
- Small
- Medium
- Large
---
Quit
```

目前選中的 preset 要 checked。選擇 preset 後立即套用 widget，並保存到 config。

## Config

`size_preset` 新的允許值：

```text
small
medium
large
```

預設值改為：

```json
"size_preset": "large"
```

V2.04 不新增額外 config 版本欄位，也不保留 V2.03 舊 `small` 的語意。Preset table 直接重排：

| V2.03 preset key | V2.04 preset key |
| --- | --- |
| `mini` | `small` |
| `compact` | `medium` |
| `current` | `large` |

也就是說，如果舊 config 已經存了 `"small"`，V2.04 會把它當成新的 Small，也就是原本的 Mini 尺寸。這是刻意接受的簡化，不做額外版本欄位。未知值 fallback 到 `large`。

## 測試

需要更新或新增測試：

- Config default 是 `large`。
- `mini / compact / current` 這些 V2.03 舊 key 會套到對應的新 key。
- `small` 保持 `small`，代表 V2.04 新 Small。
- Widget `SIZE_PRESETS` 只包含 `small / medium / large`。
- Widget default 是 `large`，尺寸是 `420x112`。
- Small / Medium / Large 套用後寬高、font、lyric line count、controls slot 都符合 profile。
- Tray Size submenu 只顯示 Small / Medium / Large。
- 選擇 Medium / Small 會呼叫 callback 並保存新的 preset value。
- Main startup 會套用 normalized config preset。
- Full suite 通過。

## 版本邊界

這是 V2.04。V2.03 保留為「四段 size presets 的首次實作」，V2.04 是基於實機視覺 review 後的 preset 收斂與命名修正。

## 實作紀錄

- Branch：`codex/v2.04-three-size-presets`
- Full suite：`223 passed`（2026-06-07）
- 下一步：看實際 Small / Medium / Large 畫面，必要時只調整尺寸/profile 數值。
