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
