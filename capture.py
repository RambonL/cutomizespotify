"""Log Spotify desktop network activity via CDP, so the hide request can be found.

Records only method, URL and request body. Headers are never requested and never
stored, because they carry the bearer and client tokens. Query parameters whose
name looks credential-ish are masked as well.

Run Spotify with:  spotify --remote-debugging-port=9222
Then:              .venv/bin/python capture.py
"""

import asyncio
import json
import sys
from urllib.request import urlopen
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
LOG_PATH = "capture.log"

# Telemetry and asset chatter drowns out the interesting calls.
NOISE = ("/events", "/metrics", "/gabo-receiver", "i.scdn.co", "audio-ak", "/ping")
SECRET_PARAMS = ("token", "auth", "secret", "key", "password")


def mask_url(url):
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = [(k, "<redacted>" if any(s in k.lower() for s in SECRET_PARAMS) else v)
             for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def page_target():
    with urlopen(f"{CDP_HTTP}/json", timeout=5) as resp:
        targets = json.load(resp)
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        sys.exit("Kein Page-Target. Läuft Spotify mit --remote-debugging-port=9222?")
    # xpui is the actual player UI; prefer it if several pages are open.
    return next((t for t in pages if "xpui" in t["url"]), pages[0])["webSocketDebuggerUrl"]


def emit(log, kind, text):
    line = f"[{kind}] {text}"
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


async def main():
    ws_url = page_target()
    log = open(LOG_PATH, "a")
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        print(f"Mitschnitt läuft -> {LOG_PATH}. Jetzt 'Ausblenden' klicken. Strg-C beendet.\n")

        async for raw in ws:
            msg = json.loads(raw)
            method, params = msg.get("method"), msg.get("params", {})

            if method == "Network.requestWillBeSent":
                req = params["request"]
                url = req["url"]
                if any(n in url for n in NOISE):
                    continue
                emit(log, req["method"], mask_url(url))
                if req.get("postData"):
                    emit(log, "body", req["postData"][:2000])

            elif method in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived"):
                # Never filtered: the outgoing write is what we are hunting for.
                payload = params.get("response", {}).get("payloadData", "")
                if payload:
                    tag = "ws>" if method.endswith("Sent") else "ws<"
                    emit(log, tag, payload[:2000])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGestoppt.")
