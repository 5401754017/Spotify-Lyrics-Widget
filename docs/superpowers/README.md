# Superpowers Docs

> 文件用途：這個資料夾是 agent 實作過程留下的 spec、plan、handoff 紀錄，不是產品發布頁來源。

Canonical current sources:

- Product/release copy: `../product-release.md`
- User install quickstart: `../../README.md`
- Development handoff/status: `../../spotify_lyrics_widget.md`
- Current taskbar/controller design: `specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md`
- Current controller lifecycle plan: `plans/2026-06-23-spotify-widget-controller-lifecycle.md`
- Why widget playback controls were removed: `plans/2026-06-20-widget-hover-settings-controls.md`

Rules for reading this folder:

- `plans/` are implementation records. After the work is done, they are historical unless marked canonical.
- `specs/` explain design decisions. Prefer the newest file that explicitly says it is canonical.
- `handoffs/` are short-lived session handoffs and may be obsolete after implementation finishes.
- Old V2 playback-control docs are historical only. The current widget hover controls are settings, hide, and close.
- Current release format is installer-only. Portable zip docs are historical unless a future plan revives them.
