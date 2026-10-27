---
title: cutomizespotify README
---

# cutomizespotify

Stream Deck buttons for the Spotify desktop client on Linux:

- **Hide** the playing track ("Don't play this"), then skip to the next one. The ban is stored server-side, so it applies on every device.
- **Like** the playing track.

The official Web API has no endpoint for hiding tracks. `hide.py` connects to the desktop client's Chrome DevTools Protocol (CDP) debug port instead and calls the client's own `FeedbackAPI`, which is the same code path as the context-menu button. It needs no token or OAuth app, and it doesn't rebuild the protocol.

## Requirements

- Spotify desktop client, started with `--remote-debugging-port=9222`
- Python 3.11+
- `websockets` for `hide.py`, `cdp.py` and `capture.py`
- `playerctl` and a logged-in [spotify_player](https://github.com/aome510/spotify-player) for `like.py`

```sh
python -m venv .venv
.venv/bin/pip install websockets
```

> **Security note:** the debug port only listens on localhost, but any local process can use it to fully control the Spotify client, including its tokens. Only enable it on a single-user machine.

## Usage

```sh
.venv/bin/python hide.py            # hide current track and skip
.venv/bin/python hide.py --check    # show only, change nothing

python3 like.py                     # like current track
python3 like.py --check             # show only
python3 like.py --selftest          # test parsers offline
```

Exit codes: `0` success, `1` error, `2` nothing playing or the current context doesn't support hiding.

Hiding only works in algorithmic or editorial contexts such as daylists, Discover Weekly and radio.

## Files

| File | Purpose |
|---|---|
| `hide.py` | Hide and skip the current track via CDP |
| `like.py` | Like the current track via the official Web API (`PUT /v1/me/tracks`), using the token cached by `spotify_player` |
| `cdp.py` | Run JavaScript in the client renderer (`-f file.js` avoids shell quoting) |
| `capture.py` | CDP network capture for diagnostics. It never logs headers and masks credential-like query parameters. |
| `docs/endpoint.md` | How hiding works internally (German) |

## Caveats

Spotify updates change module IDs and the bundler. `hide.py` finds the registry and interface IDs at runtime, so it survives most updates, but a larger refactor can still break it.

This project uses an undocumented internal client API. Use it at your own risk.
