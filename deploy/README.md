# Deployment (systemd)

These units replace the fragile openbox-autostart `&` launches with supervised services that
**restart automatically** on crash (`Restart=always`).

> Edit the paths/user in the unit files first — they assume the repo is cloned at
> `/home/pi/ipod_spotify_rasp2w` and the app runs as user `pi`.

## 1. Build the click-wheel driver
```sh
make -C clickwheel        # produces clickwheel/click (needs pigpio installed)
```

## 2. Provide Spotify credentials
`spotifypod.service` loads `frontend/.env` via `EnvironmentFile`. Create it from the template:
```sh
cp frontend/.env.example frontend/.env && nano frontend/.env   # fill SPOTIPY_* values
```

## 3. Install and enable the services
```sh
sudo cp deploy/systemd/spotifypod.service /etc/systemd/system/
sudo cp deploy/systemd/click.service      /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now click.service
sudo systemctl enable --now spotifypod.service
```

Logs: `journalctl -u spotifypod -f` and `journalctl -u click -f`.

## Caveats
- **X display:** the UI is a Tkinter app and needs an X server on `DISPLAY=:0`. This repo's
  `README.md` boots X via `startx` from `~/.bash_profile` → openbox. `spotifypod.service` waits on
  `graphical.target`; depending on how your X session starts you may need to tweak `After=`/
  `Environment=DISPLAY=` or run it as a `--user` service instead. If the service races the X
  server, the simplest fallback is to keep launching the UI from the openbox `autostart` and use
  only `click.service` under systemd.
- **pigpiod:** if your setup uses the pigpio daemon, enable it (`sudo systemctl enable pigpiod`)
  and add the dependency noted in `click.service`.
- **First run after upgrade:** clear the old Redis cache once (`redis-cli flushdb`) — the cache
  format changed from pickle to JSON.
