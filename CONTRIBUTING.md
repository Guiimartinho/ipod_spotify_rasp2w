# Contributing

Thanks for helping improve sPot! This is a fork of
[dupontgu/retro-ipod-spotify-client](https://github.com/dupontgu/retro-ipod-spotify-client) —
see [CREDITS.md](./CREDITS.md).

## Development

```sh
cd frontend
python -m unittest discover -s tests     # stdlib-only, no install required
```

For the full picture (architecture, gotchas, what's covered by tests), read [`CLAUDE.md`](./CLAUDE.md)
and the audit in [`.docs/AUDIT.md`](./.docs/AUDIT.md).

Keep new logic **testable**: put pure logic in a module that does **not** import
tkinter / PIL / spotipy / redis at top level (those are imported lazily), and add a
`frontend/tests/test_*.py` (a `unittest.TestCase`, so it runs under both `unittest` and `pytest`).

## Commit conventions

- Messages in **English**, GitHub/Conventional style (imperative subject, e.g.
  `feat(frontend): add search pagination`).
- **Atomic, sequential commits** — one logical change per commit.
- Default branch is **`main`**.
- Do not commit secrets — provide Spotify credentials via `.env` (see `frontend/.env.example`).

## CI

GitHub Actions runs the test suite on every push and pull request across Python 3.9–3.12.
Please make sure `python -m unittest discover -s tests` is green before opening a PR.
