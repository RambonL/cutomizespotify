---
title: cutomizespotify
tags:
  - spotify
  - streamdeck
  - desktop
---

# cutomizespotify

Stream-Deck-Button, der den laufenden Spotify-Song **ausblendet** ("Nicht mehr abspielen") und weiterspringt. Der Ban liegt serverseitig am Account, wirkt also auch am Handy.

Stand und nächste Schritte: [[cutomizespotify/plan-hide-button|plan-hide-button]] · Wie der Hide intern funktioniert: [[cutomizespotify/docs/endpoint|endpoint]]

> [!info] Läuft lokal, nicht auf dem Server
> Reines Desktop-Tool am CachyOS-Rechner. Kein Docker, kein `scp` nach ramboserver, kein Eintrag in [[ramboserver]].

## Der Trick

Die offizielle Web API kennt kein Hide, und der Write der Desktop-App geht durch eine native Bridge — nachbauen scheitert. Stattdessen redet `hide.py` über den **CDP-Debug-Port** direkt mit der laufenden App und ruft deren eigene `FeedbackAPI` auf. Damit braucht es **keinen Token**: kein `sp_dc`, kein OAuth, kein TOTP.

Der Web-Player kann das nicht — dort ist dieselbe API ein Stub mit `canBan: false`. Es muss die Desktop-App sein, und sie muss laufen.

> [!warning] Der Debug-Port ist eine offene Tür
> `~/.local/share/applications/spotify.desktop` startet Spotify dauerhaft mit `--remote-debugging-port=9222`. Der Port lauscht nur auf localhost, gibt aber **jedem lokalen Prozess volle Kontrolle über die Spotify-App** samt Zugriff auf deren Tokens. Auf einem Einzelplatzrechner vertretbar, auf einer Maschine mit fremden Nutzern nicht. Rückbau: die Datei löschen, dann greift wieder der System-Eintrag.

## Dateien

- `hide.py` — das Tool. `--check` liest nur. Exit 0 = ausgeblendet, 1 = Fehler, 2 = nichts läuft bzw. Kontext kann kein Hide.
- `cdp.py` — JS im Renderer ausführen. `-f datei.js` umgeht Shell-Quoting, was bei größeren Snippets nötig ist.
- `capture.py` — Netzwerk-Mitschnitt per CDP. Nur noch Diagnosewerkzeug, falls Spotify den Mechanismus umbaut.
- `.venv/` — `websockets`. Sonst nichts, alles andere ist Stdlib.

## Konventionen

- Doku deutsch, Code und Commit-Messages englisch.
- Obsidian-Markdown: Wikilinks mit Pfad und Alias `[[projekt/datei|datei]]`, Callouts, Tasks `- [ ]`, Frontmatter mit `title` + Block-Tags.
- Erkenntnisse über die interne API gehören nach `docs/endpoint.md`, nicht in Code-Kommentare.
- `capture.py` protokolliert bewusst **keine Header** — dort stecken Bearer- und Client-Token. Token-verdächtige URL-Parameter werden maskiert. Diese Zurückhaltung nicht wegoptimieren.
- Kein Over-Engineering: kein Retry-Framework, kein Config-System, keine Abstraktion über drei Aufrufe.

## Bekannte Fallstricke

- **Hide gibt es nicht überall.** Nur in algorithmischen/redaktionellen Kontexten (daylist, Discover Weekly, Radio). Sonst meldet `hide.py` Exit 2 statt zu bannen.
- **Modul-IDs wechseln mit jedem Spotify-Update.** `hide.py` sucht Registry und Interface-IDs deshalb zur Laufzeit. Bricht es trotzdem, sitzt der Fehler in dieser Suchheuristik — Details in [[cutomizespotify/docs/endpoint|endpoint]].
- **Spotify muss laufen.** Ohne Prozess kein Debug-Port und keine API. `hide.py` prüft den Port vorab und meldet per Notification statt in einen Traceback zu laufen — am Stream Deck sieht man sonst gar nichts.
- **streamdeck-ui startet keine Shell.** Command ohne Fish, ohne `~/.profile`, ohne Environment. Absolute Pfade, inklusive vollem Pfad zum venv-Python.
