# Spotify Widget V3 Portable Onboarding Design

## Current Decision

V3 should make the app easy for public users to try without knowing Python. The release target is an installer-free portable zip that contains an executable. Users download, unzip, and run `SpotifyLyricsWidget.exe`.

"Portable" in V3 means no Python installation and no command-line setup. It does not mean every user setting must live next to the executable. Config and logs should remain under `%APPDATA%/spotify-lyrics-widget/` so they survive app folder replacement during updates.

## Public Spotify Constraint

For a public release, the app should not depend on sharing the developer's own Spotify `client_id`.

Spotify Development Mode is limited and requires users to be allowlisted. Extended quota mode is the route for wider public use, but the current Spotify requirements make that unrealistic for this project at this stage. V3 therefore uses a first-run onboarding dialog that helps each user create their own Spotify app and paste their own `client_id`.

Relevant official docs:

- Spotify apps: `https://developer.spotify.com/documentation/web-api/concepts/apps`
- Quota modes: `https://developer.spotify.com/documentation/web-api/concepts/quota-modes`
- Redirect URI rules: `https://developer.spotify.com/documentation/web-api/concepts/redirect_uri`

## User Experience

First run should show a real PyQt dialog instead of the current plain text input prompt.

The dialog should be simple and action-oriented:

```text
+------------------------------------------------+
| Spotify Setup                                  |
+------------------------------------------------+
| 1. Open Spotify Developer Dashboard            |
|    [Open Dashboard]                            |
|                                                |
| 2. Add this Redirect URI to your Spotify app   |
|    http://127.0.0.1:8888/callback              |
|    [Copy Redirect URI]                         |
|                                                |
| 3. Paste your Client ID                        |
|    [____________________________]              |
|                                                |
|              [Cancel] [Connect Spotify]        |
+------------------------------------------------+
```

The dialog should not try to automate Spotify account setup. It should open the Dashboard on demand, copy the redirect URI on demand, validate that a non-empty Client ID was entered, save it to config, then continue into the existing OAuth flow.

The wording should assume the user is not a developer, but it should avoid long tutorial text inside the app. The release zip can include a short `README.md` as a fallback.

## Architecture

Add a small first-run setup dialog module and keep the existing auth flow.

Proposed components:

- `src/onboarding.py`: PyQt dialog for first-run setup.
- `src/main.py`: replace the current `QInputDialog.getText(...)` path with the onboarding dialog.
- `src/config.py`: keep current `%APPDATA%` config behavior.
- `README.md`: short fallback guide copied into the release zip.
- Packaging files: PyInstaller spec and build script for a one-folder portable zip.

No new auth protocol is needed. The app already uses PKCE and `http://127.0.0.1:8888/callback`, which matches Spotify's loopback redirect guidance.

## Data Flow

```text
User opens exe
  |
Config loads from %APPDATA%/spotify-lyrics-widget/config.json
  |
client_id missing?
  |
Yes -> show onboarding dialog
  |
User opens dashboard, copies redirect URI, pastes Client ID
  |
Dialog saves client_id through Config.save()
  |
Existing OAuth flow starts
  |
Tokens and preferences stay in %APPDATA%
```

When `client_id` already exists, startup should skip onboarding and behave like the current app.

## Packaging

Use PyInstaller one-folder output first. This is less fragile for PyQt6 than a single-file executable and is easier to debug when assets or Qt plugins are missing.

Release shape:

```text
SpotifyLyricsWidget-v3-portable/
  SpotifyLyricsWidget.exe
  _internal/
  README.md
```

The dashboard button should open `https://developer.spotify.com/dashboard`.

The build must include:

- PyQt6 runtime and Qt plugins.
- `assets/fonts/NotoSansTC-VF.ttf`.
- Existing source package under `src`.
- No console window for normal app launch.

The generated `dist/` and release zip are build artifacts and should stay out of git.

## Testing

Add focused tests before implementation:

- Missing `client_id` opens onboarding instead of `QInputDialog`.
- Accepted onboarding saves the Client ID and continues startup.
- Cancelled onboarding exits without starting workers.
- Existing `client_id` skips onboarding.
- Redirect URI text in onboarding matches `src.auth.REDIRECT_URI`.
- Packaging command can produce a one-folder build.

Manual smoke test for the final portable build:

1. Build the portable folder.
2. Run the exe from a clean config directory.
3. Verify onboarding appears.
4. Verify Open Dashboard opens the Spotify dashboard.
5. Verify Copy Redirect URI copies `http://127.0.0.1:8888/callback`.
6. Paste a Client ID and finish OAuth.
7. Confirm tray, lyrics, size menu, logging, and clean shutdown still work.
8. Replace the app folder with a rebuilt one and confirm config persists.

## Deferred

- Full data-portable mode where config/log live beside the exe.
- Single-file PyInstaller executable.
- Code signing.
- Installer/MSIX.
- Shared project-owned Spotify Client ID with extended quota.
- Rich multi-page wizard with screenshots.

These are intentionally deferred because the first public usability gap is Python-free launch plus clear Spotify setup guidance.
