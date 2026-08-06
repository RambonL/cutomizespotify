"""Evaluate JavaScript inside the running Spotify desktop client via CDP.

The client's writes go through a native Cosmos bridge, invisible to HTTP
capture. Reaching that bridge means running code in the renderer instead.

Usage:  .venv/bin/python cdp.py '<javascript expression>'
        .venv/bin/python cdp.py -f <datei.js>     # umgeht Shell-Quoting
"""

import asyncio
import json
import sys
from urllib.request import urlopen

import websockets

CDP_HTTP = "http://127.0.0.1:9222"


def page_target():
    with urlopen(f"{CDP_HTTP}/json", timeout=5) as resp:
        targets = json.load(resp)
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        raise RuntimeError("Kein Page-Target. Läuft Spotify mit --remote-debugging-port=9222?")
    return next((t for t in pages if "xpui" in t["url"]), pages[0])["webSocketDebuggerUrl"]


async def evaluate(expression):
    async with websockets.connect(page_target(), max_size=None) as ws:
        await ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        }))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("id") == 1:
                return msg.get("result", {})


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "-f":
        with open(sys.argv[2]) as fh:
            expression = fh.read()
    else:
        expression = sys.argv[1]
    try:
        result = asyncio.run(evaluate(expression))
    except RuntimeError as err:
        sys.exit(str(err))
    if "exceptionDetails" in result:
        print("FEHLER:", result["exceptionDetails"].get("text"), file=sys.stderr)
        print(json.dumps(result["exceptionDetails"].get("exception", {}), indent=2), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result.get("result", {}).get("value"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
