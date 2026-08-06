---
title: plan-hide-button
tags:
  - spotify
  - streamdeck
  - plan
---

# plan-hide-button

Weg vom leeren Ordner zum funktionierenden Stream-Deck-Button: ein Druck → Song ausgeblendet, Playback springt weiter, Wirkung auch am Handy.

Kontext und Fallstricke: [[cutomizespotify/CLAUDE|cutomizespotify]] · Protokoll-Details: [[cutomizespotify/docs/endpoint|endpoint]]

## Phase 1 — Recon ✅

- [x] Spotify mit `--remote-debugging-port=9222` gestartet, CDP antwortet
- [x] `capture.py` gebaut, Netzwerk mitgeschnitten (ohne Header)
- [x] Hide-Mechanismus identifiziert: Collection-Set `playcontextbans`, Ban pro Track **und** Kontext
- [x] Ergebnis: der Write geht durch die native Cosmos-Bridge, ist per CDP-Network unsichtbar → **HTTP-Nachbau verworfen**

## Phase 2 — Zugriffsweg ✅

Der ursprüngliche Plan (`sp_dc`-Token, OAuth-App) ist damit hinfällig. Kein Token nötig, die App macht den Call selbst.

- [x] Webpack-`require` über `webpackChunkclient_web.push` geholt
- [x] Service-Registry im React-Fiber-Baum gefunden
- [x] `FeedbackAPI` aufgelöst, `canBan: true` bestätigt
- [x] `PlayerAPI` aufgelöst für Track, Kontext und Skip
- [x] Modul-IDs werden zur Laufzeit gesucht statt hartkodiert

## Phase 3 — `hide.py` ✅

- [x] `cdp.py` als JS-Brücke (`-f datei.js` umgeht Shell-Quoting)
- [x] `hide.py`: Track lesen → `addContextTrackBan(context, track, 1)` → `skipToNext()`
- [x] Exit-Codes 0 / 1 / 2, Rückmeldung per `notify-send`
- [x] `--check` als Selbsttest, liest nur und verändert nichts
- [x] Scharf getestet: Song ausgeblendet, Playback sprang weiter

## Phase 4 — Stream Deck

- [x] Desktop-Eintrag `~/.local/share/applications/spotify.desktop` überschreibt den System-Eintrag und startet Spotify immer mit dem Debug-Port
- [ ] Taste in streamdeck-ui anlegen, Feld *Command*:
      `/home/rambo/Projekte/cutomizespotify/.venv/bin/python /home/rambo/Projekte/cutomizespotify/hide.py`
- [ ] Icon setzen
- [ ] Einmal Spotify komplett neu starten, damit der Desktop-Eintrag greift

> [!warning] streamdeck-ui startet keine Shell
> Der Command läuft ohne Fish, ohne `~/.profile`, ohne dein Environment. Absolute Pfade, keine Aliase, keine Variablen-Expansion — deshalb der volle Pfad zum venv-Python.

## Offen

- [ ] Handy-Wirkung gegenprüfen: ausgeblendeten Song suchen, taucht er in der daylist am Handy noch auf?
- [ ] Un-Hide als zweite Taste — `removeContextTrackBan` existiert, ungetestet
- [x] `capture.py` behalten — Diagnosewerkzeug für den Tag, an dem Spotify den Mechanismus umbaut
- [x] `capture.log` gelöscht, steht in `.gitignore`
