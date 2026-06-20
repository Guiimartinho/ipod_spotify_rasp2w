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

## Formatting & linting

The project uses [black](https://github.com/psf/black) (formatter), [ruff](https://github.com/astral-sh/ruff)
(linter + import sorting), and [mypy](https://github.com/python/mypy) (type checker), all configured
in `pyproject.toml` / `frontend/mypy.ini`. Apply them before committing:

```sh
pip install -r frontend/requirements-dev.txt
ruff check --fix frontend
black frontend
mypy --config-file frontend/mypy.ini frontend
```

Or let [pre-commit](https://pre-commit.com) run them automatically:

```sh
pip install pre-commit && pre-commit install
```

## CI

GitHub Actions runs on every push and pull request and **all checks must be green**: the test suite
across Python 3.9–3.12, `ruff`, `black --check`, and `mypy`. With the pre-commit hooks installed
(`pre-commit install`), ruff + black run automatically on every commit, so CI failures are rare.
