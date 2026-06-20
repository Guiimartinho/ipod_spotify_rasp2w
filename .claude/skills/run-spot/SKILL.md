---
name: run-spot
description: Run the sPot Spotify iPod frontend locally for development or to verify a change. Use when asked to run, start, launch, test, or smoke-check the sPot app (spotifypod.py) outside the Raspberry Pi. Handles Redis, the SPOTIPY_* OAuth env vars, the .cache token, and keyboard-instead-of-clickwheel controls.
---

# Run sPot (development)

The sPot frontend (`frontend/spotifypod.py`) is a Tkinter app. It can run on a desktop
(macOS/Linux/Windows-with-display) without the iPod click-wheel hardware — keyboard keys map to
the same navigation handlers (`onKeyPress`). Audio is **not** produced locally; on a desktop you
are exercising the UI, navigation, Spotify Web API calls, and Redis cache only.

## Preconditions (check before running)
1. **Redis must be running** on `localhost:6379` (default). `datastore.py` connects at import.
   - macOS: `brew install redis && redis-server`
   - Debian/Ubuntu/Raspbian: `sudo apt install redis-server` (service usually auto-starts)
   - Windows: run `redis-server` (Memurai/WSL) or use a container; verify with `redis-cli ping` → `PONG`.
2. **Python deps:** `cd frontend && pip3 install -r requirements.txt`.
   Note: Deps are unpinned. If install pulls Pillow ≥10, `Image.ANTIALIAS` in `spotifypod.py:59`
   crashes at startup — pin `Pillow==8.4.0` (or patch to `Image.LANCZOS`).
3. **Spotify OAuth env vars** must be set (spotipy reads them implicitly):
   ```sh
   export SPOTIPY_CLIENT_ID=...
   export SPOTIPY_CLIENT_SECRET=...
   export SPOTIPY_REDIRECT_URI=http://127.0.0.1
   ```
   Create the app at https://developer.spotify.com/dashboard. First run opens a browser for the
   OAuth flow and writes a `.cache` token into the **current working directory** (gitignored).

## Run
Always launch from the `frontend/` directory — image assets are loaded with paths relative to CWD:
```sh
cd frontend
python3 spotifypod.py
```
On `darwin` the window is forced to 320×240; elsewhere it tries fullscreen (`-fullscreen`).

## Controls without the click-wheel
Input normally arrives as UDP packets on `127.0.0.1:9090` from `click.c`. For desktop dev, use the
**keyboard fallback** — read `onKeyPress` in `spotifypod.py` for the exact key bindings (menu/back,
select/center, play, next/prev, and scroll up/down).

## Seeing real content
Menus are empty until the library has been synced into Redis at least once. To populate it, run
`spotify_manager.refresh_data()` once (per README step 11, temporarily set it in `view_model.py:17`
in place of `refresh_devices()`), then revert. Without it, only device discovery works.

## Smoke test (no GUI)
To verify wiring without a display:
```sh
cd frontend && python3 -c "import datastore; datastore.Datastore().r.ping(); print('redis ok')"
```

## If it fails
- Hang/blocking at startup → `view_model.py:17` `refresh_devices()` and the `spotify_manager`
  import make blocking network/Redis calls. Confirm Redis is up and env vars are set.
- `Image.ANTIALIAS` AttributeError → Pillow too new (see preconditions).
- No display ($DISPLAY unset over SSH) → Tk needs a display/X server.
