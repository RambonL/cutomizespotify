---
title: endpoint
tags:
  - spotify
  - reverse-engineering
---

# endpoint

Wie der Hide-Button intern funktioniert und warum der Zugriff über CDP läuft. Umsetzung: [[cutomizespotify/plan-hide-button|plan-hide-button]]

> [!info] Aufnahmebedingungen
> Spotify 1.2.92.147 (Arch-Paket, CEF/Chromium 146), gestartet mit `--remote-debugging-port=9222`, mitgeschnitten per CDP durch `capture.py`. Header wurden bewusst nie protokolliert.

## Hide ist ein Collection-Set

Der Hide-Button schreibt einen Eintrag ins Collection-Set **`playcontextbans`**. Über den Dealer-WebSocket kam die Server-Bestätigung zurück:

```
uri: hm://collection/playcontextbans/<user-hash>/json
```

```json
{"items":[{
  "type": "track",
  "removed": false,
  "identifier": "4PG1YD5lYIZHVUleqUceVo",
  "contextUri": "spotify:playlist:37i9dQZEVXcOadNSYcOL6e",
  "itemData": {"playContextBansItemData": {"itemProvider": "PROVIDER_CONTEXT"}}
}]}
```

Der Ban gilt **pro Track *und* Kontext**, nicht global. Derselbe Song in einer anderen Playlist bleibt spielbar — das erklärt, warum Hide nur in algorithmischen Kontexten angeboten wird. Neben `playContextBansItemData` kennt das Protokoll auch `banItemData` und `artistbanItemData`, also globalen Ban und Künstler-Ban.

## Warum HTTP-Nachbau nicht geht

Im Mitschnitt tauchte **kein einziges gesendetes Frame** auf, nur die Antwort. Der Write verlässt die App durch die native Cosmos-Bridge (`window.sendCosmosRequest`), nicht durch den CEF-Renderer — für CDP-Network damit unsichtbar.

Der generische Collection-Writer im Bundle wäre `POST <spclient>/collection/v2/write` mit `{username, set, items:[{uri}]}`, aber der Kontext-Ban geht einen eigenen Weg (`banInPlayContext`), und ohne gesehenen Request wird der Rest Raterei. Deshalb: gar nicht erst nachbauen.

## Der Weg, der funktioniert

Statt das Protokoll nachzubilden, ruft [[cutomizespotify/CLAUDE|hide.py]] die App-eigene API im Renderer auf — per CDP `Runtime.evaluate`. Kette:

1. `webpackChunkclient_web.push(…)` liefert die Webpack-`require`-Funktion.
2. Der React-Fiber-Baum wird per Breitensuche nach dem `RegistryProvider` durchsucht — erkennbar an `memoizedProps.value.resolve`. Nach ~24 Knoten gefunden.
3. Interface-IDs kommen aus dem Bundle-Code über das Muster `.u)("<Name>")`.
4. `registry.resolve(iid("PlayerAPI"))` und `registry.resolve(iid("FeedbackAPI"))`.

Relevante Signaturen (Desktop-Implementierung, Klasse `cH`):

```js
feedback.getCapabilities()                              // {canBan: true}
feedback.addContextTrackBan(contextUri, itemUri, 1)     // 1 = PROVIDER_CONTEXT
feedback.removeContextTrackBan(contextUri, itemUri)     // Un-Hide
player.getState()                                       // .item.uri, .context.uri, .item.name
player.skipToNext()
```

Im Web-Player ist dieselbe Klasse ein Stub (`Method not implemented`, `canBan: false`) — deshalb fehlt dort der Button, und deshalb muss es die Desktop-App sein.

> [!warning] Modul-IDs sind flüchtig
> `74933`, `83888`, `56358` und Co. stammen aus genau diesem Build. `hide.py` hartkodiert sie deshalb nicht, sondern sucht Registry und Interface-IDs zur Laufzeit. Bricht es nach einem Spotify-Update trotzdem, ist die Suchheuristik (`.u)("…")` bzw. `memoizedProps.value.resolve`) die Stelle zum Nachziehen.

## Un-Hide

`removeContextTrackBan(contextUri, itemUri)` ist der Gegenpart, im Code vorhanden, aber noch nicht ausprobiert. Braucht zusätzlich eine Quelle für die Kontext-URI, wenn der Song nicht mehr läuft.
