# Spotify Lyrics Widget - Product Release Source

> Canonical use: this is the source document for product pages, release pages, and public-facing feature copy.
>
> Do not use `docs/superpowers/plans/*`, `docs/superpowers/specs/*`, or `spotify_lyrics_widget.md` directly for product copy. Those files contain historical implementation notes and may mention removed features.

## Product Summary

Spotify Lyrics Widget is a Windows desktop app that keeps the currently playing Spotify track and synced lyrics visible in a small always-on-top widget.

The app is built for people who want lyrics on screen while working, writing, streaming, studying, or using another full-screen-ish app without switching back to Spotify.

## Current Product Experience

- Floating desktop lyrics widget for Spotify on Windows.
- Shows current track, artist, synced lyric line, and playback progress.
- Keeps a compact always-on-top widget on the desktop.
- Supports three fixed widget sizes: Small, Medium, and Large.
- Hovering over the widget shows settings, hide, and close controls.
- Long track titles marquee on hover and stay neatly elided when idle.
- Taskbar controller provides a stable Windows taskbar entry.
- Controller can run, show, hide, and close the widget.
- System tray appears while the widget is running and can open/hide or close the widget.
- First run guides the user through Spotify Client ID setup.
- Installer lets the user choose English or Traditional Chinese for first-run setup.
- Configuration and logs persist under `%APPDATA%/spotify-lyrics-widget`.

## Lyrics Sources

- LRCLIB is the primary synced lyrics source.
- NetEase is used as a fallback when LRCLIB has no synced lyrics or is temporarily unavailable.
- Chinese NetEase fallback results are matched across Traditional/Simplified variants and displayed in Traditional Chinese.
- Temporary lyric lookup failures are not cached as permanent "no lyrics" results.

## Install And Setup

1. Download `SpotifyLyricsWidgetSetup.exe`.
2. Run the installer and choose the first-run setup language.
3. Launch `SpotifyLyricsWidget.exe` from the Start Menu or desktop shortcut.
4. In the first-run setup window, open Spotify Dashboard and create a Spotify app.
5. Add this Redirect URI:

```text
http://127.0.0.1:8888/callback
```

6. Copy the Spotify App Client ID back into the setup window.
7. Authorize Spotify in the browser.

## What Not To Say On Product Pages

- Do not describe the widget as a playback remote.
- Do not mention previous / play-pause / next widget controls; they were removed from the current UI.
- Do not present portable zip as the release format; the current release is installer-only.
- Do not advertise startup-on-boot, Mac, Linux, lyrics translation, Genius, Musixmatch, playlist add, or single-file exe.
- Do not use old V1/V2/V3 implementation phase wording in public copy.

## Suggested Short Copy

Spotify Lyrics Widget puts synced Spotify lyrics in a compact always-on-top desktop widget for Windows. It stays out of the way, keeps the current line visible, and gives you a taskbar controller to show, hide, or close the widget whenever you need.

## Suggested Feature Bullets

- Synced Spotify lyrics on your desktop
- Compact always-on-top widget
- Small, Medium, and Large size presets
- Taskbar controller for show, hide, run, and close
- First-run Spotify setup guide
- English and Traditional Chinese setup language
- LRCLIB primary lyrics with NetEase fallback
- Logs and settings stored in `%APPDATA%`

## Current Limitations

- Windows only.
- Requires the user to create their own Spotify App Client ID.
- Requires Spotify authorization in the browser.
- No code signing yet, so antivirus or SmartScreen warnings may happen.
- Current build is a one-folder app installed through Inno Setup, not a single-file exe.

## Document Map

- User install quickstart: `README.md`
- Product/release copy source: `docs/product-release.md`
- Development handoff and version state: `spotify_lyrics_widget.md`
- Agent plan/spec history: `docs/superpowers/README.md`
