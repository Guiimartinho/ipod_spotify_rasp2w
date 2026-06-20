# Frontend

To run: `python3 spotifypod.py`

## Dependencies

First, you'll need to install the dependencies via `pip3`:

```sh
pip3 install -r requirements.txt
```

For local development on macOS, you need to install redis:

```sh
brew install redis
```

## Authentication

You'll need to authenticate with Spotify to get an access token, which will sit in a file called `.cache`.

To generate the `.cache` file, you need the following enviroment variables: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET` and `SPOTIPY_REDIRECT_URI`.
More information regarding the authentication flow can be found in **spotipy**'s instructions [here](https://spotipy.readthedocs.io/en/2.16.1/#authorization-code-flow).

And to more information how to get a Spotify `CLIENT_ID`, `CLIENT_SECRET` and to set a `REDIRECT_URI` visit the Spotify Docs section *Register Your App* [here](https://developer.spotify.com/documentation/general/guides/app-settings/).

Copy `.env.example` to `.env` and fill in the three `SPOTIPY_*` values (it also documents the
optional `SPOT_REDIS_*` and `SPOT_LOG_LEVEL` overrides).

### How authentication & token refresh works

You never handle a Spotify access token by hand, and **no token is ever stored in the code**. The
app uses spotipy's Authorization Code flow, which refreshes the short-lived access token for you:

```
You register an App in the Spotify dashboard
        │  gives you CLIENT_ID + CLIENT_SECRET   (these do NOT expire)
        ▼
frontend/.env   (SPOTIPY_CLIENT_ID / SECRET / REDIRECT_URI)        ← gitignored
        ▼
spotipy.SpotifyOAuth   ── first run: opens a browser, you authorize once
        ▼
frontend/.cache   (stores the access token + refresh token)        ← gitignored
        ▼
access token expires after ~1 hour
        │  spotipy automatically uses the refresh token to get a new one,
        ▼  before every API call — no code of ours, no manual step
always-valid token  ──►  Spotify Web API
```

The wiring is a single line in `spotify_manager.py`:

```python
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope), ...)
```

Passing `SpotifyOAuth` as the `auth_manager` is what makes spotipy check expiry and refresh the
token automatically. So:

- **What you provide:** `CLIENT_ID` / `CLIENT_SECRET` / `REDIRECT_URI` in `.env` (the client secret
  does not expire). You authorize once in a browser to create `.cache`.
- **What stays secret and out of git:** `.env` (your credentials) and `.cache` (the tokens). Both
  are in `.gitignore`. Never paste a raw access token into the code — those are temporary (~1h) and
  spotipy manages them for you.
- **Expiry handling:** automatic. The 1-hour access token is refreshed indefinitely via the
  long-lived refresh token in `.cache`, with no intervention. (If you ever change the requested
  `scope`, delete `.cache` and re-authorize once.)

## Tests

The test suite is stdlib-only — no third-party packages or running Redis required:

```sh
python -m unittest discover -s tests
```

It also runs under `pytest` (`pip install -r requirements-dev.txt && pytest`). See the *Testing*
section of the top-level `CLAUDE.md` for what is and isn't covered.

## Notes

`spotifypod.py` has a `main()` / `if __name__ == "__main__"` entry point — importing it has no side
effects. The first run after upgrading from the pickle-based cache should start with an empty Redis
(`redis-cli flushdb`) so the library repopulates in the new JSON format.
