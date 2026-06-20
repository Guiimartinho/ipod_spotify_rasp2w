# CLAUDE.md — sPot (iPod Spotify Client)

Guidance for Claude Code when working in this repository.

## What this project is

**sPot** turns a 2004 4th-gen **iPod Classic** into a Spotify Connect client. All software
runs on a **Raspberry Pi Zero W** hidden inside the iPod shell. The original click-wheel is
read by a C driver; a Python/Tkinter UI reproduces the classic iPod menu on the original
screen; actual audio is played by **raspotify (librespot)**, a separate Spotify Connect
daemon — *this repo never plays audio itself*, it only controls playback via the Spotify Web API.

- Upstream: https://github.com/dupontgu/retro-ipod-spotify-client
- Project writeup: https://hackaday.io/project/177034-spot-spotify-in-a-4th-gen-ipod-2004
- This checkout is a **fork being actively improved/fixed** (working tree clean, branch `master`).
- The original author self-describes the code as "a mess / learning Python" — treat it as a
  hobby codebase: pragmatic fixes over perfection, but there is real tech debt (see AUDIT).

## Repository layout

```
/
├── frontend/                 # the Python/Tkinter app (runs as user `pi`)
│   ├── spotifypod.py         # UI: Tk frames, render loop, UDP input, screen sleep/wake; main()
│   ├── view_model.py         # MVVM page/menu models + Rendering snapshots
│   ├── spotify_manager.py    # spotipy wrapper: auth, library sync, playback, bg thread, start()
│   ├── datastore.py          # Redis cache of Spotify objects (JSON, lazy/injectable client)
│   ├── config.py             # shared constants (UDP, button codes, pins, colors, redis, sizes)
│   ├── serialization.py      # JSON ser/deser registry for domain objects (replaced pickle)
│   ├── input_decoder.py      # pure WheelDecoder: UDP packet -> nav events (unit-tested)
│   ├── tests/                # stdlib-only test suite (unittest + fake redis + mocks)
│   ├── requirements.txt      # spotipy/redis/Pillow — now PINNED
│   ├── requirements-dev.txt  # pytest (suite also runs on bare stdlib)
│   ├── .env.example          # SPOTIPY_* + optional SPOT_REDIS_* / SPOT_LOG_LEVEL
│   ├── pytest.ini
│   ├── *.png / *.ppm / *.bmp # UI assets (arrows, play/pause, wifi, progress frame)
│   └── README.md             # dev/run + Spotify auth notes
├── clickwheel/
│   ├── click.c               # C driver: reads click-wheel via pigpio, sends UDP events
│   └── Makefile              # build/install the driver
├── .docs/sPot_schematic.png  # hardware wiring diagram
├── .docs/AUDIT.md            # full code audit: bugs, security, deps, roadmap + fix status
├── README.md                 # full Raspberry Pi install/deploy guide
└── LICENSE                   # GPL-3.0
```

> **Cache format changed (pickle → JSON).** A Redis cache written by the old code is
> not readable by the new code. After upgrading, clear Redis (or run a full
> `refresh_data()`) once to repopulate — see the migration note below.

## Architecture & data flow

```
iPod click-wheel (hardware)
   │  serial bitstream on GPIO  (CLOCK=23, DATA=25; haptic motor on 26)
   ▼
click.c  ── pigpio ISRs decode 32-bit packets, pulse haptic on scroll
   │  UDP datagram → 127.0.0.1:9090   3 bytes = [buttonBit, state, wheelPos(0-255)]
   ▼
spotifypod.py (Tk UI)  ── app_main_loop() polls the UDP socket via select(),
   │                       processInput() → onXxxPressed() → page.nav_*()
   ▼
view_model.py  ── Page tree (RootPage → Artists/Albums/Playlists/Shows/Search/NowPlaying);
   │              page.render() returns a Rendering snapshot the UI draws
   ▼
spotify_manager.py ──spotipy/SpotifyOAuth──► Spotify Web API  (HTTPS, library + transport)
   │                 (bg_loop daemon thread polls "now playing")
   ▼
datastore.py ──pickle──► redis-server (localhost:6379)   [library cache]

Audio (independent):  Spotify Web API ──start_playback(device_id)──► raspotify/librespot ──► speaker
                       (target device = the one whose name contains "Spotifypod")
```

### Key facts that are NOT obvious from a quick read
- **Input IPC is a UDP loopback socket on port 9090.** `click.c` `sendto()`s 3-byte packets;
  `spotifypod.py` binds `127.0.0.1:9090` non-blocking and polls with `select()`. Button bit
  codes are shared *by convention* between the two files: center=7, right/next=8, left/prev=9,
  down/play=10, up/back=11, wheel-touch=29. **Changing a code in one file requires changing the other.**
- **Imports are now side-effect-free.** All startup work (refresh + `bg_loop` thread) happens in
  `spotify_manager.start()`, called from `spotifypod.main()`. The spotipy client and the `redis`
  client are created lazily on first use, and `import spotipy` / `import redis` are deferred — so
  the modules import without those packages installed (this is what makes the test suite run on a
  bare Python). Do **not** reintroduce network calls or thread starts at module top level.
- **The library is empty until `refresh_data()` runs at least once.** Boot normally only runs
  `refresh_devices()` (via `start()`). To fully sync, call `spotify_manager.start(refresh_full=True)`
  or run `refresh_data()` once.
- **One shared spotipy client, now thread-safe.** `bg_loop` and user actions both use the module
  `sp`, which is a locking proxy (`_SpotifyProxy` + re-entrant `_sp_lock`) — every call is
  serialized because requests' session is not thread-safe. Keep using `sp`; don't bypass it.
- **Redis stores JSON** (via `serialization.py`), not pickle. The cache is still tied to the domain
  class names (the `@serialization.register` types in `spotify_manager.py`) — renaming a class
  invalidates old cache entries, but there is no longer an RCE risk from `pickle.loads`.

## Running it (development, off the Pi)

The UI can run on macOS/Linux for development (Tk + a local Redis), without the click-wheel
(use keyboard fallback — see `onKeyPress` in `spotifypod.py`).

```sh
# 1. Redis
brew install redis && redis-server          # macOS;  or: sudo apt install redis-server
# 2. Python deps (consider pinning — see AUDIT)
cd frontend && pip3 install -r requirements.txt
# 3. Spotify OAuth — set these, then first run opens a browser to create ./.cache
export SPOTIPY_CLIENT_ID=...                 # from https://developer.spotify.com/dashboard
export SPOTIPY_CLIENT_SECRET=...
export SPOTIPY_REDIRECT_URI=http://127.0.0.1
# 4. Run from the frontend/ dir (asset paths are relative to CWD!)
python3 spotifypod.py
```

Keyboard controls map to the same handlers as the wheel (see `onKeyPress`). On the Pi the app
runs fullscreen; on `darwin` it forces a 320×240 window.

### Building the click-wheel driver
```sh
cd clickwheel && make        # gcc -Wall -O2 -pthread -o click click.c -lpigpio -lrt
sudo ./click                 # needs root: pigpio uses direct peripheral/DMA access
sudo ./click -v              # verbose: print decoded packets (debug)
```

## Testing

The test suite is **stdlib-only** — it runs on a bare Python with no third-party packages,
because the production modules defer `import spotipy` / `import redis` / `import PIL` and the
tests use an in-repo fake Redis (`tests/fake_redis.py`) plus `unittest.mock`.

```sh
cd frontend
python -m unittest discover -s tests          # bare stdlib, runs anywhere
# or, if pytest is installed (pip install -r requirements-dev.txt):
pytest
```

What's covered: `serialization` round-trips, `datastore` (incl. degraded/Redis-down mode),
`input_decoder` wheel+button logic, `view_model` navigation/paging/search-results math, and
`spotify_manager` parsing/playback/refresh with a mocked spotipy client (incl. the bug-fix
regressions). **Not** covered by automated tests (validate on-device): the Tkinter rendering in
`spotifypod.py` (needs a display) and the C bit-decode in `click.c` (needs the hardware).

When you add logic, keep it testable: put pure logic in a module that doesn't import
tkinter/PIL/spotipy/redis at top level, and add a `tests/test_*.py` (a `unittest.TestCase`, so it
runs under both `unittest` and `pytest`).

## Conventions & gotchas when editing

- **Run the app from `frontend/`** — image assets are loaded with paths relative to the CWD,
  with no existence check. Prefer `os.path.dirname(__file__)` if you touch asset loading.
- **Pillow:** `spotifypod.py` uses `Image.ANTIALIAS`, removed in Pillow ≥10 → replace with
  `Image.LANCZOS`/`Image.Resampling.LANCZOS` if you bump Pillow.
- **`render()` must stay cheap and ideally side-effect-free**, but today some pages trigger
  playback *inside* `render()` (`view_model.py` NowPlaying/SingleTrack) — be careful not to
  add work that runs every redraw.
- **Wrap new Spotify/Redis calls in try/except.** Only `get_now_playing` is currently guarded;
  most network/cache calls are unguarded and can crash a worker thread.
- **GPIO pin numbers and button codes are duplicated** between `click.c` and `spotifypod.py`/
  `view_model.py`. Keep them in sync (ideally centralize them — see roadmap).
- Platform branching keys off `sys.platform == 'darwin'` for dev vs Pi.

## Known issues & what to improve

The full, prioritized audit with file:line and **fix status** lives in **`.docs/AUDIT.md`**.

**Fixed in this branch** (code + regression tests):
- `get_album_tracks` wrong endpoint; `StopIteration` in now-playing lookup; bare `except: pass`;
  unguarded playback/library/Redis calls (now logged, degraded); thread-unsafe spotipy client
  (locking proxy); pickle→JSON (no more RCE); `Image.ANTIALIAS` (Pillow ≥10 compat); CWD-relative
  asset paths; import-time side effects; mutable default args; `lru_cache` staleness/leak; pinned
  deps; `.env.example`; logging instead of `print`; `clickwheel/Makefile`; click.c busy-wait,
  `main` signature, `MSG_CONFIRM`, `volatile` ISR globals, debug gating.

**Still open (need owner action / hardware):**
- (high) **Rotate the upstream-leaked Spotify credentials.** A real `client_id`/`client_secret` was
  hard-coded in an earlier upstream version and still lives in the *upstream* public history. This
  repo was published with a **fresh history** so the secrets are not carried over — but the exposed
  app should still be rotated/deleted in the Spotify dashboard. Do not re-import the old history.
- (med) **Harden Redis**: bind to `127.0.0.1` + `requirepass` (deployment/config, not code).
- (med) raspotify stores the Spotify password in plaintext (`/etc/default/raspotify`); `chmod 600`.
- (low) Wheel-range reconciliation (C sends 0-255 vs Python thresholds) was intentionally **left
  unchanged** — it's calibrated to the hardware; verify/tune on the device.
- (low) systemd unit with `Restart=always` instead of the openbox `&` autostart; CI; type hints.

## Migration note (important)
This branch changed the Redis serialization from **pickle to JSON**. An existing cache from the
old code is unreadable by the new code. On first run after upgrading, **clear Redis once**
(`redis-cli flushdb`, or just let `refresh_data()` run — it clears its own keys first) so the
library repopulates in the new format.
