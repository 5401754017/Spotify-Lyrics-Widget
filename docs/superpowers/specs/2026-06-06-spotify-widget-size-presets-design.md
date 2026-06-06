# Spotify Lyrics Widget Size Presets Design

Date: 2026-06-06
Status: Draft for user review

## Goal

Add fixed widget size presets so the widget can take less desktop space without
making the UI fragile. This is a density preset feature, not freeform resize and
not pure proportional scaling.

The current `420x112` widget remains the largest/default size. Smaller presets
reduce width, height, padding, gaps, and lyric font size in controlled steps.
Mini mode is the most compact mode and shows only one lyric line with ellipsis.

## Non-goals

- No freeform drag resize.
- No continuous scale slider.
- No content-driven auto-resize.
- No change to the playback-control behavior.
- No change to lyric lookup, cache, or timing.

## Presets

| Preset | Window | Title font | Lyric font | Lyric lines | Purpose |
| --- | --- | --- | --- | --- | --- |
| Current | `420x112` | `10pt` | `16pt` | 2 | Existing layout; maximum size |
| Compact | `380x96` | `10pt` | `14pt` | 2 | Smaller but still comfortable |
| Small | `340x84` | `9pt` | `12pt` | 2 | Dense daily-use layout |
| Mini | `300x74` | `8pt` | `10pt` | 1 | Extreme compact layout |

If implementation screenshots show clipping, revise this spec before changing
the values. The important contract is the preset shape: fixed width/height,
fixed font sizes, fixed lyric line count.

## Layout Rules

Each preset owns a complete layout profile:

- Widget width and height.
- Panel margins.
- Top row height.
- Gap between title and lyric lane.
- Lyric lane height.
- Progress bar height.
- Transport-control cluster size and position.
- Close-button size and position.
- Title and lyric font sizes.
- Maximum lyric visual lines.

The UI should not calculate arbitrary intermediate sizes. It should apply one
profile at a time, then reposition overlay controls using that profile.

Mini mode uses a one-line lyric clamp. If the lyric does not fit, it is elided
with `...`, matching the current clipping style. Current, Compact, and Small
keep the existing two-visual-line lyric behavior.

## Switching UX

Add a `Size` submenu to the existing tray menu:

```text
Size
- Current
- Compact
- Small
- Mini
```

Selecting an item immediately applies the preset and saves it to config. The
selected preset should be checked in the tray menu. On next launch, the widget
restores the saved preset.

No resize handle is added. No keyboard shortcut is required for the first
version.

## Config

Add a persisted `size_preset` value.

Default:

```json
"size_preset": "current"
```

Accepted values:

```text
current
compact
small
mini
```

If config contains an unknown value, fall back to `current` and save only when
the user chooses a valid preset later. This avoids surprising file writes during
startup.

## Implementation Shape

`src/widget.py` should define a small preset data structure and one method to
apply a preset to the widget. The method updates fixed size, margins, row
heights, fonts, button sizes, control positions, and lyric line count.

`src/lyric_clamp.py` should support the requested maximum visual line count.
Current behavior is equivalent to `max_lines=2`; Mini uses `max_lines=1`.

`src/tray.py` should expose a size submenu and emit or call a callback when the
user picks a preset. `src/main.py` wires the tray callback to the widget and
config save.

## Testing

Add or update tests for:

- Config default and persistence for `size_preset`.
- Widget applies each preset's fixed width/height, font sizes, and lyric line
  count.
- Mini lyric text clamps to one visual line with ellipsis.
- Current/Compact/Small keep two-line lyric clamp behavior.
- Tray menu contains a `Size` submenu with four selectable presets.
- Selecting a preset updates the widget and persists config.

Full suite verification is required before marking the feature complete.

## Version Boundary

This should be a V2.03 UI polish feature if implemented before V3 packaging. It
is a user-visible feature but does not change the project direction.
