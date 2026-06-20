# Credits

sPot is a fork of **[dupontgu/retro-ipod-spotify-client](https://github.com/dupontgu/retro-ipod-spotify-client)**
by **Guy Dupont**, accompanying the
[Hackaday project "sPot: Spotify in a 4th-gen iPod (2004)"](https://hackaday.io/project/177034-spot-spotify-in-a-4th-gen-ipod-2004).

The **full original commit history is preserved in this repository** — every commit below this
fork's improvements is the work of the original authors. Their contributions made this project
possible.

> The only change to the original history is that a Spotify `client_id`/`client_secret` which had
> been accidentally committed upstream was **redacted** from the historical commits, so no secret
> is carried into this repository. Nothing else about the original commits was altered.

## Original authors & contributors

(from the upstream commit history; commit counts are mailmap-consolidated)

- [**Guy Dupont** (@dupontgu)](https://github.com/dupontgu) — original author / project creator
- [**André Silva** (@ElCapitanDre)](https://github.com/ElCapitanDre)
- [**Utku Tarhan** (@utkut)](https://github.com/utkut)
- [**rsappia** (@rsappia)](https://github.com/rsappia)
- [**3urobeat** (@3urobeat)](https://github.com/3urobeat)
- [**Mitch Lui** (@mitchLui)](https://github.com/mitchLui)
- [**Tom** (@tomaculum)](https://github.com/tomaculum)
- **Tobias Herrmann**

## License

This project is licensed under the **GPL-3.0**, inherited from the upstream project. See
[`LICENSE`](./LICENSE). All original copyrights are retained.

## This fork

Re-targeted at the **Raspberry Pi Zero 2 W** and hardened (pinned dependencies, JSON cache,
thread-safe Spotify client, error handling, structured logging, a stdlib-only test suite, CI, and
systemd units). See [`CLAUDE.md`](./CLAUDE.md) and [`.docs/AUDIT.md`](./.docs/AUDIT.md).
