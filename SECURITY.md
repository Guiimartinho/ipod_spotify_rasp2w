# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting instead: go to the
[**Security** tab](https://github.com/Guiimartinho/ipod_spotify_rasp2w/security/advisories) and click
**“Report a vulnerability”**. This opens a private advisory visible only to the maintainers.

We'll acknowledge the report as soon as we can and keep you updated on the fix.

## Scope & threat model

sPot is a single-user gadget: it runs on a Raspberry Pi inside an iPod, on the owner's home
network. Some "issues" are accepted trade-offs for that context (running under X, the click-wheel
driver needing root for GPIO). Still relevant and in scope:

- **Credential handling.** Spotify credentials (`SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET`) and
  the OAuth `.cache` token must never be committed. They are provided via environment / `.env`
  (gitignored). See `frontend/.env.example`.
- **Redis.** The cache stores JSON (not pickle), so there is no deserialization RCE. Still, bind
  Redis to `127.0.0.1` and set a password in production — see `.docs/AUDIT.md` §1.
- **raspotify** stores the Spotify account password in plaintext at `/etc/default/raspotify`;
  `chmod 600` it and keep the device off untrusted networks.

## Never commit secrets

If you accidentally commit a credential:

1. **Rotate it immediately** (e.g. regenerate the Spotify app secret in the
   [developer dashboard](https://developer.spotify.com/dashboard)) — assume it is compromised the
   moment it's pushed.
2. Then remove it from history (`git filter-repo` / BFG). Rotation comes first; scrubbing history
   does **not** un-leak an already-pushed secret.

> Historical note: an upstream version of this project once committed a real Spotify
> `client_id`/`client_secret`. Those values were scrubbed from the history imported into this
> repository, and this repo contains no secrets. See `.docs/AUDIT.md`.

## Supported versions

This project tracks a single `main` branch; security fixes land there. There are no separately
maintained release branches.
