"""Lock screen widgets: what hyprlock shows bottom left, one line each.

    python3 -m lennox.lockinfo [all|music|weather|alarm|phone|server]

Only reads what's already known (no waiting on the network): the weather
from the widgets' cache, the server from the bar's last check. Lennox
Settings > Widgets > Lock screen turns each line on or off.
"""

import json
import os
import subprocess
import sys
import time

from . import clock as C
from . import settings as S

PHONE_CACHE = os.path.join(S.RUNTIME_DIR, "lock-phone.json")
PHONE_EVERY = 60
LINES = ["music", "alarm", "weather", "phone", "server"]


def esc(text):
    """hyprlock labels are Pango markup."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(argv, timeout=3):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def music():
    out = _run(["playerctl", "metadata", "--format", "{{status}}\t{{title}}\t{{artist}}"])
    parts = out.split("\t")
    if len(parts) != 3 or parts[0] not in ("Playing", "Paused") or not parts[1]:
        return ""
    icon = "󰎈" if parts[0] == "Playing" else "󰏤"
    return f"{icon}  {esc(parts[1])}" + (f"  ·  {esc(parts[2])}" if parts[2] else "")


def alarm(now=None, data=None):
    now = time.time() if now is None else now
    try:
        up = C.next_up(data if data is not None else C.load(), now)
    except (OSError, ValueError, KeyError):
        return ""
    if not up:
        return ""
    kind, item, left = up
    if kind == "alarm":
        label = f"  ·  {esc(item['label'])}" if item.get("label") else ""
        return f"󰀠  Alarm {time.strftime('%H:%M', time.localtime(item['next']))}{label}"
    if kind == "timer":
        return f"󰔛  {esc(item.get('label') or 'Timer')}  ·  {C.countdown(left)} left"
    if left <= 12 * 3600:
        return f"󰃰  {time.strftime('%H:%M', time.localtime(item['at']))}  ·  {esc(item.get('text', ''))}"
    return ""


def weather(now=None):
    from .widgets import data as D        # no GTK needed: just the cache
    now = time.time() if now is None else now
    entry = D._read_cache().get("forecast") or {}
    w = entry.get("data")
    if not w or now - entry.get("time", 0) > 3 * 3600:
        return ""
    return f"󰖐  {w['temp']}{w['unit']}  ·  {esc(w['text'])}  ·  {esc(w['place'])}"


def phone(now=None):
    """The first connected phone's battery (asked once a minute at most)."""
    now = time.time() if now is None else now
    try:
        with open(PHONE_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if now - cached["time"] < PHONE_EVERY:
            return cached["text"]
    except (OSError, ValueError, KeyError):
        pass
    text = ""
    out = _run([os.path.expanduser("~/.local/bin/lennox-phone"), "status"], timeout=8)
    try:
        for d in json.loads(out).get("devices", []):
            if d.get("paired") and d.get("reachable") and d.get("battery") is not None:
                text = f"󰏲  {esc(d['name'])}  ·  {d['battery']}%" + ("  󱐋" if d.get("charging") else "")
                break
    except (ValueError, AttributeError):
        pass
    try:
        os.makedirs(os.path.dirname(PHONE_CACHE), exist_ok=True)
        with open(PHONE_CACHE, "w", encoding="utf-8") as f:
            json.dump({"time": now, "text": text}, f)
    except OSError:
        pass
    return text


def server(now=None):
    from .mcserver import STATE
    now = time.time() if now is None else now
    try:
        if now - os.path.getmtime(STATE) > 600:
            return ""
        with open(STATE, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return ""
    if not info.get("online"):
        return ""
    name = info.get("address", "").split(".")[-2].capitalize() if info.get("address", "").count(".") else ""
    names = ", ".join(info.get("names") or [])
    return f"󰍳  {esc(name)}  ·  {info.get('players', 0)} online" + (f"  ({esc(names)})" if names else "")


PARTS = {"music": music, "alarm": alarm, "weather": weather, "phone": phone, "server": server}


def lines(settings):
    lock = settings["lockscreen"]
    if not lock["widgets"]:
        return []
    out = []
    for name in LINES:
        if lock[name]:
            try:
                text = PARTS[name]()
            except Exception:  # noqa: BLE001  one broken line must not blank the rest
                text = ""
            if text:
                out.append(text)
    return out


def main(argv):
    what = argv[1] if len(argv) > 1 else "all"
    settings = S.load()
    if what == "all":
        print("\n".join(lines(settings)))
    elif what in PARTS:
        print(PARTS[what]())
    else:
        print(f"usage: lennox-lockinfo all | {' | '.join(PARTS)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
