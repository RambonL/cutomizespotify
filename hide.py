"""Blendet den laufenden Spotify-Song aus ("Nicht mehr abspielen") und springt weiter.

Läuft über den CDP-Debug-Port der Desktop-App und ruft deren eigene FeedbackAPI
auf — derselbe Weg, den der Hide-Button im Kontextmenü nimmt. Kein Token, kein
Nachbau des Protokolls.

    spotify --remote-debugging-port=9222
    .venv/bin/python hide.py            # ausblenden + weiter
    .venv/bin/python hide.py --check    # nur anzeigen, ändert nichts

Exit: 0 = ausgeblendet, 1 = Fehler, 2 = es läuft nichts / Kontext kann kein Hide.
"""

import asyncio
import shutil
import subprocess
import sys
from urllib.request import urlopen

from cdp import CDP_HTTP, evaluate

# Modul-IDs wechseln mit jedem Spotify-Update, deshalb wird alles zur Laufzeit
# gesucht: die Registry über den React-Baum, die Interface-IDs über den Bundle-Code.
BOOTSTRAP = """
  let req;
  webpackChunkclient_web.push([[Symbol("hide")], {}, (r) => { req = r; }]);

  const iid = (name) => {
    const needle = '.u)("' + name + '")';
    for (const k of Object.keys(__webpack_modules__)) {
      if (String(__webpack_modules__[k]).includes(needle)) {
        const v = Object.values(req(k))[0];
        if (v) return v;
      }
    }
    throw new Error("Interface-ID nicht gefunden: " + name);
  };

  const el = document.querySelector("#main") || document.body;
  const key = Object.keys(el).find((k) => k.startsWith("__reactFiber$") || k.startsWith("__reactContainer$"));
  if (!key) throw new Error("Kein React-Fiber am DOM");
  let registry = null;
  const queue = [el[key]];
  let seen = 0;
  while (queue.length && seen < 60000 && !registry) {
    const fiber = queue.shift();
    seen++;
    if (typeof fiber.memoizedProps?.value?.resolve === "function") registry = fiber.memoizedProps.value;
    if (fiber.child) queue.push(fiber.child);
    if (fiber.sibling) queue.push(fiber.sibling);
  }
  if (!registry) throw new Error("Service-Registry nicht gefunden");

  const player = registry.resolve(iid("PlayerAPI"));
  const feedback = registry.resolve(iid("FeedbackAPI"));
  const state = await player.getState();
  const track = state?.item?.uri;
  const context = state?.context?.uri;
  const title = state?.item?.name ?? state?.item?.metadata?.title ?? track;
"""

CHECK_JS = f"""(async () => {{
{BOOTSTRAP}
  return {{status: track ? "bereit" : "nichts_laeuft", track, context, title,
           canBan: feedback.getCapabilities().canBan}};
}})()"""

# PROVIDER_CONTEXT aus dem ItemProvider-Enum der App: der Ban gilt für diesen Kontext.
HIDE_JS = f"""(async () => {{
{BOOTSTRAP}
  if (!track) return {{status: "nichts_laeuft"}};
  if (!context) return {{status: "kein_kontext", title}};
  if (!feedback.getCapabilities().canBan) return {{status: "kein_ban", title}};
  await feedback.addContextTrackBan(context, track, 1);
  await player.skipToNext();
  return {{status: "ok", track, context, title}};
}})()"""


def notify(text, urgency="normal"):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", urgency, "-a", "Spotify", text], check=False)


def port_offen():
    """Ohne Debug-Port gibt es keine App-API — das ist der häufigste Fehlerfall."""
    try:
        with urlopen(f"{CDP_HTTP}/json/version", timeout=2):
            return True
    except OSError:
        return False


def run(js):
    result = asyncio.run(evaluate(js))
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description")
                           or result["exceptionDetails"].get("text"))
    return result.get("result", {}).get("value")


def main():
    check = "--check" in sys.argv
    if not port_offen():
        grund = "Spotify nicht erreichbar — läuft es, und mit Debug-Port 9222?"
        print(grund, file=sys.stderr)
        notify(grund, "critical")
        return 1

    try:
        res = run(CHECK_JS if check else HIDE_JS)
    except Exception as err:
        print(f"Fehler: {err}", file=sys.stderr)
        notify(f"Ausblenden fehlgeschlagen: {err}", "critical")
        return 1

    status = res.get("status")
    if check:
        print(res)
        return 0 if status == "bereit" else 2

    if status == "ok":
        print(f"Ausgeblendet: {res['title']}")
        notify(f"Ausgeblendet: {res['title']}")
        return 0

    grund = {
        "nichts_laeuft": "Es läuft gerade nichts.",
        "kein_kontext": "Kein Playlist-Kontext — hier gibt es kein Ausblenden.",
        "kein_ban": "Dieser Kontext unterstützt kein Ausblenden.",
    }.get(status, f"Unerwartet: {res}")
    print(grund, file=sys.stderr)
    notify(grund, "critical")
    return 2


if __name__ == "__main__":
    sys.exit(main())
