## Summary

<!-- What does this PR change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Docs
- [ ] CI / tooling

## Checklist

- [ ] Tests pass locally: `cd frontend && python -m unittest discover -s tests`
- [ ] New logic has a `tests/test_*.py` (and stays importable without spotipy/redis/PIL/tkinter)
- [ ] No secrets committed (credentials go in `.env`, see `frontend/.env.example`)
- [ ] Commit messages follow the conventions in [CONTRIBUTING.md](../CONTRIBUTING.md) (English, imperative, atomic)
- [ ] If GPIO pins or click-wheel button codes changed, both `clickwheel/click.c` and `frontend/config.py` were updated

## Hardware tested?

<!-- Pi Zero 2 W + iPod? Desktop (Tk + keyboard fallback) only? Not tested on hardware? -->
