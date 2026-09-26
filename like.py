"""Liked den laufenden Spotify-Song ("Zu Lieblingssongs hinzufügen").

Geht über die offizielle Web API (`PUT /v1/me/tracks`) — anders als beim
Ausblenden kennt sie dafür einen Endpunkt, CDP ist also nicht nötig. Das
OAuth-Token kommt aus dem Cache, den `spotify_player` beim Login angelegt hat;
der Scope `user-library-modify` steckt bereits drin. Die Track-ID liefert
`playerctl` über MPRIS.

    python3 like.py             # liken
    python3 like.py --check     # nur anzeigen, ändert nichts
    python3 like.py --selftest  # Parser prüfen, ohne Netz

Exit: 0 = geliked bzw. war schon geliked, 1 = Fehler, 2 = es läuft kein Track.
"""

import json
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN_FILE = Path.home() / ".cache/spotify-player/user_client_token.json"
CONFIG_FILE = Path.home() / ".config/spotify-player/app.toml"
API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# MPRIS liefert /com/spotify/track/<22 Zeichen Base62>. Werbung und lokale
# Dateien haben ein anderes Präfix und dürfen nicht als Track durchgehen.
TRACK_ID = re.compile(r"^/com/spotify/track/([A-Za-z0-9]{22})$")


def notify(text, urgency="normal"):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", urgency, "-a", "Spotify", text], check=False)


def track_id(mpris_trackid):
    """Track-ID aus der MPRIS-trackid, oder None wenn es kein normaler Track ist."""
    treffer = TRACK_ID.match(mpris_trackid.strip())
    return treffer.group(1) if treffer else None


def abgelaufen(expires_at):
    """expires_at ist RFC3339 mit bis zu 9 Nachkommastellen, fromisoformat kann nur 6."""
    stempel = re.sub(r"\.(\d{6})\d*", r".\1", expires_at.replace("Z", "+00:00"))
    return datetime.fromisoformat(stempel) <= datetime.now(timezone.utc)


def playerctl(feld):
    ergebnis = subprocess.run(["playerctl", "-p", "spotify", "metadata", feld],
                              capture_output=True, text=True, timeout=5)
    return ergebnis.stdout.strip() if ergebnis.returncode == 0 else ""


def token_holen():
    """Token aus dem spotify_player-Cache, bei Ablauf per refresh_token erneuert."""
    daten = json.loads(TOKEN_FILE.read_text())
    if not abgelaufen(daten["expires_at"]):
        return daten["access_token"]

    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": daten["refresh_token"],
        "client_id": tomllib.loads(CONFIG_FILE.read_text())["client_id"],
    }).encode()
    anfrage = urllib.request.Request(
        TOKEN_URL, data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        neu = json.load(antwort)

    daten["access_token"] = neu["access_token"]
    daten["expires_in"] = neu["expires_in"]
    daten["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=neu["expires_in"])
                           ).isoformat().replace("+00:00", "Z")
    # Bei PKCE schickt Spotify meist einen neuen refresh_token, aber nicht immer.
    daten["refresh_token"] = neu.get("refresh_token", daten["refresh_token"])
    TOKEN_FILE.write_text(json.dumps(daten))
    return daten["access_token"]


def api(methode, pfad, token, params):
    url = f"{API}{pfad}?{urllib.parse.urlencode(params)}"
    anfrage = urllib.request.Request(url, method=methode,
                                     headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        rohtext = antwort.read()
    return json.loads(rohtext) if rohtext else None


def selftest():
    assert track_id("/com/spotify/track/3nrXEbXIdxVHhpMTt9ZSKz") == "3nrXEbXIdxVHhpMTt9ZSKz"
    assert track_id("/com/spotify/track/3nrXEbXIdxVHhpMTt9ZSKz\n") == "3nrXEbXIdxVHhpMTt9ZSKz"
    assert track_id("/com/spotify/ad/1234") is None
    assert track_id("/org/mpris/MediaPlayer2/TrackList/NoTrack") is None
    assert track_id("") is None
    assert abgelaufen("2020-01-01T00:00:00.123456789Z")
    assert abgelaufen("2020-01-01T00:00:00Z")
    assert not abgelaufen("2099-01-01T00:00:00.220769026Z")
    print("selftest ok")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    check = "--check" in sys.argv

    if not shutil.which("playerctl"):
        print("playerctl fehlt", file=sys.stderr)
        return 1

    tid = track_id(playerctl("mpris:trackid"))
    if not tid:
        grund = "Kein Track — läuft Spotify, und ist es gerade keine Werbung?"
        print(grund, file=sys.stderr)
        notify(grund, "critical")
        return 2

    titel = playerctl("xesam:title") or tid
    try:
        token = token_holen()
        if check:
            print(f"{titel}: {'geliked' if api('GET', '/me/tracks/contains', token, {'ids': tid})[0] else 'nicht geliked'}")
            return 0
        api("PUT", "/me/tracks", token, {"ids": tid})
    except urllib.error.HTTPError as fehler:
        grund = f"Spotify antwortet {fehler.code}: {fehler.read().decode(errors='replace')[:200]}"
        print(grund, file=sys.stderr)
        notify(f"Like fehlgeschlagen: {grund}", "critical")
        return 1
    except (OSError, KeyError, ValueError) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        notify(f"Like fehlgeschlagen: {fehler}", "critical")
        return 1

    print(f"Geliked: {titel}")
    notify(f"Geliked: {titel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
