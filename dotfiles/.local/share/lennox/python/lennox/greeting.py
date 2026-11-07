"""Startup greeting: a short hello at login with what matters today.

    python3 -m lennox.greeting [show|text]

`show` says it in the island and in a notification (the login script runs it
once a little after the desktop is up); `text` just prints it. Lennox Settings >
Daily care > Greeting turns it off.
"""

import datetime
import getpass
import sys

from . import care as C
from . import focus as F
from . import lockinfo as L
from . import settings as S
from . import sh


def hello(hour):
    if hour < 5:
        return "Still up"
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def lines(settings, now=None):
    """[(headline, [detail lines])] for the greeting, using only what is already known."""
    now = now or datetime.datetime.now()
    name = settings["greeting"]["name"].strip() or getpass.getuser().capitalize()
    head = f"{hello(now.hour)}, {name}"
    details = []
    weather = L.weather(now.timestamp())
    if weather:
        details.append(weather)
    if settings["care"]["prayer"]:
        prayer = C.prayer_line(now, settings)
        if prayer:
            details.append("󰥔  " + prayer)
    up = L.alarm(now.timestamp())
    if up:
        details.append(up)
    streak = F.stats(F._read(F.LOG, []), now.timestamp())["streak"]
    if streak:
        details.append(f"󰈸  {streak}-day focus streak. Keep it going")
    return head, details


def main(argv):
    mode = argv[1] if len(argv) > 1 else "text"
    settings = S.load()
    if mode == "show" and not settings["greeting"]["on"]:
        return 0
    head, details = lines(settings)
    if mode == "text":
        print("\n".join([head, *details]))
    elif mode == "show":
        sh.island("face-smile-symbolic", head, 6)
        sh.notify(head, "\n".join(details) or "Have a good one.", "face-smile-symbolic")
    else:
        print("usage: lennox-greeting [text|show]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
