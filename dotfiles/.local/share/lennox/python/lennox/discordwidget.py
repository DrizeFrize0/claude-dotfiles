"""Discord server widget: how many people are online in your server.

    python3 -m lennox.discordwidget status      JSON {"ok", "name", "online", "names": [...]}

Uses the server's public widget (Server Settings > Widget > Enable server widget),
which needs no login. Asked at most every two minutes.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from . import settings as S

CACHE = os.path.join(S.CACHE_DIR, "discord.json")
MAX_AGE = 120
URL = os.environ.get("LENNOX_DISCORD_URL", "https://discord.com/api/guilds/{id}/widget.json")


def parse(data):
    members = data.get("members") or []
    return {"ok": True, "name": data.get("name", "Discord"), "online": int(data.get("presence_count", len(members))),
            "names": [m.get("username", "?") for m in members][:8]}


def status(server_id, now=None, fetch=None):
    now = time.time() if now is None else now
    if not server_id.isdigit():
        return {"ok": False, "error": "No server set"}
    try:
        with open(CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("id") == server_id and now - cached["time"] < MAX_AGE:
            return cached["data"]
    except (OSError, ValueError, KeyError):
        cached = None
    try:
        raw = (fetch or _fetch)(URL.format(id=server_id))
        data = parse(raw)
    except (OSError, ValueError, urllib.error.URLError):
        if cached and cached.get("id") == server_id:
            return cached["data"]
        return {"ok": False, "error": "The widget is off or the server wasn't found"}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump({"id": server_id, "time": now, "data": data}, f)
    return data


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Lennox"})
    with urllib.request.urlopen(req, timeout=6) as r:                       # noqa: S310  a fixed https address
        return json.load(r)


def main(argv):
    if (argv[1] if len(argv) > 1 else "status") != "status":
        print("usage: lennox-discord status", file=sys.stderr)
        return 2
    print(json.dumps(status(S.load()["discord"]["server_id"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
