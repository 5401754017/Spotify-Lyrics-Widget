# Spotify Lyrics Widget V1 Plan Follow-up Review

Date: 2026-05-22

Target plan: `2026-05-22-spotify-lyrics-widget-v1.md`

## Verdict

The revised V1 plan fixes the earlier plan blockers:

- Spotify HTTP 401 now forces refresh and retries once before re-auth.
- Re-auth creates a fresh Spotify worker instead of restarting a stopped one.
- LRCLIB 5xx / timeout paths are separated from real no-lyrics results.
- OAuth callback server binds before opening the browser.
- LRCLIB fallback matching now has a defined normalization rule and tests.
- Final manual-test staging no longer uses `git add -A`.

The plan is close to executable. Fix the remaining network-test mismatch below first.

## Remaining Plan Issue

### Offline worker tests do not exercise the code that emits the signals

Plan references:

- Spotify worker `run()` network handling around lines 925-938
- Task 10 network tests around lines 2206-2242

Current plan shape:

- `network_error` and `network_recovered` are emitted in the worker `run()` loop when `_poll_once()` raises or later succeeds.
- The new Task 10 tests call `worker._poll_once()` directly.
- Those tests do not assert `signals`, and direct `_poll_once()` currently lets `httpx.ConnectError` escape instead of emitting the signals itself.

Why this matters:

- The test snippets as written will either fail on the direct `ConnectError` or pass without proving the signals are emitted, depending on how Task 10 is implemented.
- This leaves the offline retry behavior underspecified in the plan.

Plan change:

- Pick one design and make code and tests agree.
- Option A: keep network-error handling in `run()` and add a small testable helper / one-cycle method that includes the `run()` error-state transition logic.
- Option B: move the network-error state transition into `_poll_once()` and have `_poll_once()` swallow only the network exceptions it is responsible for.
- In either option, make the tests assert that `network_error` fires on failure and `network_recovered` fires after the next successful poll.

## Small Test Improvement

In the 401 test around lines 769-799, set `token_expires_at` to a future valid timestamp. That makes the test prove a 401 forces refresh even when the local expiry clock says the token is still valid.
