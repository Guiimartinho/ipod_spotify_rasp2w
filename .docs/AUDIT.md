# sPot — Code Audit & Improvement Plan

Consolidated findings from a deep, multi-agent review of the whole codebase
(`spotifypod.py`, `view_model.py`, `spotify_manager.py`, `datastore.py`, `clickwheel/click.c`,
README/deploy). Line numbers are exact to the files as reviewed. Static analysis only — nothing
was run against live Redis/Spotify/Pi hardware.

> TL;DR severity order: **(1)** rotate leaked git-history credentials, **(2)** fix the album-tracks
> wrong-endpoint bug, **(3)** make the spotipy client thread-safe, **(4)** stop swallowing/raising
> uncaught exceptions on worker threads, **(5)** harden Redis + drop pickle.

---

## 0. Fix status (this branch)

Most code-level findings below have been **fixed**, with a stdlib-only regression test suite
(`frontend/tests/`, 49 tests, green). Remaining items are deployment/config or hardware-only.

| Status | Items |
|--------|-------|
| Fixed | B1 (album endpoint), B2 (thread-safe `sp` proxy), B3 (`StopIteration`), B4 (bare except→log), B5 (unguarded playback), B6 (div-by-zero), B7 (pagination), B8 (`pickle.loads(None)`), B9 (lru_cache), B13 (mutable default), B14 (import side effects), B15 (ANTIALIAS), S2 (pickle→JSON), C1/C4/C5 (busy-wait, `main`, `MSG_CONFIRM`), C2 (return codes), C3 (`volatile`), C6 (unsigned-char buffer), deps pinned, `.env.example`, logging, `clickwheel/Makefile`, **CI** (GitHub Actions), **systemd units**, **type hints** (all frontend modules + lenient mypy), **ruff + black + mypy** (code fully formatted/typed; all enforced as required CI checks) + **pre-commit/pre-push hooks**, **deploy hardening** (Redis loopback+password config, raspotify chmod docs) |
| Open — owner action | S1 (rotate leaked git-history credentials — dashboard), S2/S3 apply-on-device (copy `deploy/redis/spot-redis.conf`, `chmod 600 /etc/default/raspotify`) |
| Open — needs hardware | B10/B11 (wheel range/paging desync — left as-is, calibrated to hardware; verify/tune on device) |
| Backlog | full (strict) mypy coverage; auto-format pass once tools run on a dev machine |

New modules added: `config.py` (constants), `serialization.py` (JSON registry), `input_decoder.py`
(pure, testable wheel decode). Startup side effects moved into `spotify_manager.start()`.

---

## 1. Security

| # | Severity | Issue | Location | Mitigation |
|---|----------|-------|----------|-----------|
| S1 | Urgent | **A real Spotify `client_id`/`client_secret` was hard-coded in an earlier version of the upstream project** and later moved to env vars. The values are gone from the current code but remain in the *upstream* public git history (and any clone of it). | upstream history → `frontend/spotify_manager.py` (values redacted here) | **Rotate/delete that Spotify app in the dashboard.** This repo is published with a fresh history so the secrets are not carried over; do not re-import the old history. |
| S2 | Should fix | **Unauthenticated Redis + `pickle.loads` of every cached value = RCE** if any process/host can write Redis. | `datastore.py` (loads at 78,85,107,115,123,131,135,142,153) + `redis.Redis()` at :8 | Bind Redis to `127.0.0.1`, set `requirepass`. Long term: serialize JSON, not pickle. |
| S3 | Should fix | Spotify **account username/password stored in plaintext** in `/etc/default/raspotify`. | `README.md:157` | Document `chmod 600`; prefer librespot token cache over raw password. |
| S4 | Acceptable* | Whole stack runs under X as **root via `sudo`**; `click` needs root for GPIO. | `README.md:122-124` | Note risk; drop to non-root where feasible. *Acceptable for a single-user offline gadget. |
| S5 | Acceptable | Broad OAuth scopes incl. `streaming`, `playlist-modify-*`. | `spotify_manager.py:87-98` | Fine for a full-control remote; no action. |

Working tree / HEAD are clean — **no** hardcoded secrets, `.cache`/`.env` properly gitignored
(`frontend/.gitignore`). The only secret exposure is in **history** (S1).

---

## 2. Bugs & correctness (prioritized)

| # | Sev | File:Line | Bug | Fix |
|---|-----|-----------|-----|-----|
| B1 | High | `spotify_manager.py` `get_album_tracks` (~160) | Calls `sp.playlist_tracks(id)` on an **album** id → wrong endpoint, album tracks never load. | Use `sp.album_tracks(id)`. |
| B2 | High | `spotify_manager.py:102` + `bg_loop` (465-470) + `run_async` | Single global spotipy `sp` shared by the bg polling thread and user-action threads; requests session **not thread-safe** → corrupted responses / token-refresh races. | Lock around `sp` calls, or one client per thread. |
| B3 | High | `view_model.py:372-373, 383-384` | `next(x for … if val.uri == uri)` with **no default** → `StopIteration` when the playing track isn't in the cached list (local files, partial playlists) crashes the bg thread. | `next((…), -2)` + guard the index. |
| B4 | High | `spotifypod.py:574` | Bare `except: pass` in `app_main_loop` swallows **all** errors every tick — UI silently stops updating, undebuggable. | Log + narrow the exception. |
| B5 | High | `spotify_manager.py` playback calls (289,300,309,319,330,434,440,446,452) | `start_playback`/`next_track`/`pause`/… unguarded; a network blip or 403 "no active device" kills the `run_async` thread. | Wrap in try/except (+ user feedback). |
| B6 | Med | `spotifypod.py:294` | `progress_ms / now_playing['duration']` → **ZeroDivisionError** when duration is 0 (ads/some episodes). | `duration or 1`. |
| B7 | Med | `spotify_manager.py` search (411-426), `new_releases` (263), `current_user_saved_shows` (270) | **No pagination** — silently capped at the first page (≤50). | Add `sp.next()` loops. |
| B8 | Med | `datastore.py:135,142,153` | `getArtist`/`getSavedTrack`/`_getSavedItem` call `pickle.loads(None)` on a cache miss → **TypeError** (siblings guard None, these don't). | Add `None` guard before unpickling. |
| B9 | Med | `datastore.py` lru_cache (59-131) & `view_model.py:296,323` | `@lru_cache` on **instance methods** reading mutable Redis state → stale data after `refresh_data`/`clear`, never invalidated, and pins `self` (leak). | Drop lru_cache or clear it on refresh. |
| B10 | Med | `view_model.py:241-257` | Menu paging math (`nav_up`/`nav_down`) + `SearchResultsPage` header-row jumps can desync `index`/`page_start`; last item can be unreachable at boundaries. | Explicit clamping of index/page_start. |
| B11 | Med | `spotifypod.py:404-417` vs `click.c:96` | Wheel range mismatch: C sends `wheelPosition` 0-255; Python wrap logic assumes ~0-45 and `abs(Δ)>6 → reset` drops fast scrolls. | Reconcile the wheel range; relax threshold. |
| B12 | Med | `spotifypod.py:440-443` | Screen sleep/wake condition inverted; `last_interaction` updated on every packet so timeout rarely fires as intended. | Wake on any input, sleep after timeout. |
| B13 | Med | `view_model.py:33` (`lines=[]`) & `:210` (`EMPTY_LINE_ITEM`) | **Mutable default arg / shared mutable** — aliasing across renders. | `lines=None` → `[]`; don't share LineItem. |
| B14 | Low | `view_model.py:17` | `spotify_manager.refresh_devices()` runs **at import** — blocking network call, unguarded, order-dependent. | Move into an explicit `init()`. |
| B15 | Low | `spotifypod.py:59` | `Image.ANTIALIAS` removed in Pillow ≥10 → startup crash on modern Pillow. | `Image.LANCZOS`. |
| B16 | Low | `spotify_manager.py` `sleep_time` (433-470) | Global `sleep_time` written by `run_async` threads, read by `bg_loop`, no lock. | Guard or accept (benign). |

### click.c specific (all fixed; verify on the device)
| # | Sev | Line | Issue | Status |
|---|-----|------|-------|--------|
| C1 | Med | 199-201 | `while(1){};` busy-wait pins a CPU core at 100%. | Fixed: `pause()` + signal-driven `gpioTerminate`. |
| C2 | Med | 174,193,196,110 | pigpio + `sendto` return codes ignored — no error handling. | Fixed: check/`perror` returns. |
| C3 | Low | 34-43 | ISR-shared `bits`/`dataBit`/`lastBits` mutated across two alert callbacks, not `volatile`. | Fixed: marked `volatile`. |
| C4 | Low | 160 | `int main(void *args)` non-standard signature, no `return`. | Fixed: `int main(int, char**)` + return. |
| C5 | Low | 111 | `MSG_CONFIRM` on a UDP send is meaningless. | Fixed: flag dropped; sends to explicit loopback. |
| C6 | Low | 81,104 | Buffer init sentinel `-1` collides with real wheel value 255 in a signed `char`. | Fixed: `unsigned char` buffer, `0xFF` sentinel. |

> The click-wheel bit-decode math (32-bit packet parsing, wheel thresholds) was intentionally left
> unchanged — it is calibrated to the hardware. Validate the C changes on the device.

---

## 3. Dependencies, build & deployment

- **All Python deps unpinned** (`spotipy`, `redis`, `pillow`). Highest risk is **spotipy**: the
  code targets 2.16.1-era behavior (implicit env-var OAuth, result shapes, `.cache`); newer
  releases changed OAuth/cache/pagination and can break auth silently. Pillow dropped
  `ANTIALIAS` and lacks armv6 wheels (Pi Zero W) → source builds.
  **Recommended pins (Pi Zero W friendly):** `spotipy==2.16.1`, `redis==3.5.3`, `Pillow==8.4.0`.
- **No Makefile for `click.c`** — build line only exists as a comment; autostart references a
  prebuilt binary the docs never tell you to compile. Add `clickwheel/Makefile` (`build` + `install`).
- **Fragile boot chain**: console autologin → `.bash_profile` `startx` → `xinitrc` openbox →
  `/etc/xdg/openbox/autostart` launches `spotifypod.py` and `click` with `&`. Hardcoded
  `/home/pi/fork/...` paths; **no supervision** (a crash is permanent until reboot).
  `lightdm` is installed but unused (startx path is used) — contradictory.
- **`pigpiod` never enabled** in the README though `click` needs it.
- **Missing engineering:** no tests, no CI, no `pyproject.toml`/`setup.py`, no lockfile, no
  systemd units, no `.env` loading (`python-dotenv` not used though `.env` is gitignored),
  no logging config.

---

## 4. Improvement roadmap (prioritized)

### P0 — robustness & quick wins
- Pin the 3 deps; replace `Image.ANTIALIAS`→`LANCZOS`. *(S / high)*
- Replace bare `except: pass` (`spotifypod.py:574`) with logging. *(S / high)*
- Retry/backoff + token-expiry + `SpotifyException` handling wrapper around all `sp` calls. *(M / high)*
- Guard Redis (connection check + degraded mode). *(S / high)*
- Add `.env.example` for `SPOTIPY_*`; switch `print()`→`logging` (file handler, no console on Pi). *(S / med)*

### P1 — structure, resilience, tooling
- `config.py` constants module: UDP `IP/PORT`, button codes, GPIO pins (mirrored in C), `SCALE`,
  colors, fonts, `SCREEN_TIMEOUT`, `MENU_PAGE_SIZE`. Removes magic numbers & the duplicate pin defs. *(M / med)*
- Remove import-time side effects (`bg_loop` start, `refresh_devices`, `SpotifyOAuth`) into an
  explicit `init()`; replace module globals (`page`, `app`, `sleep_time`, `has_internet`) with a
  controller object. *(L / med)*
- **systemd unit with `Restart=always`** instead of openbox `&` launch; parameterize paths. *(S / high)*
- `clickwheel/Makefile`; `black` + `ruff` + `mypy` + `pre-commit` + minimal GitHub Actions CI. *(S / med)*
- Type hints + docstrings, starting with `datastore.py` and the `Rendering`/`Page` hierarchy. *(M / low)*

### P2 — testing & UX
- `pytest`: best targets are `MenuPage.nav_up/down` paging math, `SearchResultsPage` jump logic,
  and `Datastore` round-trips. Mock `spotipy.Spotify` + use `fakeredis`; needs the P1 DI refactor. *(M / med)*
- Graceful **offline/no-device screen** (a `pod_wifi.png` glyph exists; today it just
  `print("error! no devices")`). *(S / med)*
- UX grounded in existing code: now-playing screensaver instead of blank DPMS-off; battery glyph
  beside the wifi indicator; the Marquee/haptics already exist. *(S / low)*

---

## 5. Architectural notes
- Layering is reasonably clean: **UI → view-model → service → cache**, with input decoupled over
  UDP so the C driver and keyboard share the same handlers. The Rendering/subscribe pattern is a
  decent MVC-ish split.
- Biggest structural risks: import-time side effects, unsynchronized global mutable state shared
  across the Tk loop and worker threads, silent failure swallowing, and pickle-in-Redis coupling
  the cache format to Python class definitions.
