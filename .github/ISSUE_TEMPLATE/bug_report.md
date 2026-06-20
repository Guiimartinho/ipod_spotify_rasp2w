---
name: Bug report
about: Report something that isn't working
title: "[bug] "
labels: bug
---

## Describe the bug

<!-- A clear description of what's wrong. -->

## Where does it happen?

- [ ] UI / menus (`spotifypod.py`, `view_model.py`)
- [ ] Spotify / playback (`spotify_manager.py`)
- [ ] Redis cache (`datastore.py`)
- [ ] Click-wheel driver (`clickwheel/click.c`)
- [ ] Build / install / deploy

## To reproduce

1.
2.

## Expected behavior

<!-- What you expected to happen. -->

## Environment

- Device: <!-- Raspberry Pi Zero 2 W / desktop dev -->
- OS: <!-- Raspberry Pi OS version / macOS / Linux -->
- Python version: <!-- python3 --version -->
- raspotify running and a "Spotifypod" device visible? <!-- yes/no -->
- redis-server running? <!-- redis-cli ping -->

## Logs

<!-- Relevant output. On the Pi with systemd: `journalctl -u spotifypod -n 100`.
     Set SPOT_LOG_LEVEL=DEBUG for more detail. Do NOT paste tokens or client secrets. -->

```
paste logs here
```
