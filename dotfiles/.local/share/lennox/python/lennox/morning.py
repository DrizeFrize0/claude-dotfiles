"""Good-morning summary: how long you slept, the weather, your next prayer, the day's focus streak, the battery.

    python3 -m lennox.morning [show|text]

Runs by itself when the night light ends (lennox-winddown morning). Settings > Night turns it off.
"""

import datetime
import os
import sys

from . import bedtime as B
from . import greeting as G
from . import settings as S
from . import sh


def sleep_line(log, now):
    """'You stopped at 01:10, about 7.5 hours ago' from the sleep log ({night: 'HH:MM'}); '' if there is no note for last night."""
    last_night = (now - datetime.timedelta(hours=14)).date().isoformat()       # the night that just ended
    stop = log.get(last_night)
    if not stop:
        return ""
    h, m = (int(x) for x in stop.split(":"))
    night = datetime.datetime.combine(datetime.date.fromisoformat(last_night), datetime.time(h, m))
    if h < 12:
        night += datetime.timedelta(days=1)                                      # after midnight belongs to the next calendar day
    hours = (now - night).total_seconds() / 3600
    if not 1 <= hours <= 16:
        return ""
    verdict = "a good night" if hours >= 7 else "a bit short" if hours >= 5.5 else "a short night: go easy today"
    return f"You stopped at {stop}: about {hours:.1f} hours of sleep ({verdict})"


def battery_line():
    for supply in sorted(os.listdir("/sys/class/power_supply")) if os.path.isdir("/sys/class/power_supply") else []:
        base = os.path.join("/sys/class/power_supply", supply)
        if sh.read_text(os.path.join(base, "type")) == "Battery" and sh.read_text(os.path.join(base, "scope")) != "Device":
            cap = sh.read_text(os.path.join(base, "capacity"))
            if cap.isdigit():
                return f"Battery {cap}% ({sh.read_text(os.path.join(base, 'status')).lower()})"
    return ""


def lines(settings, now=None):
    now = now or datetime.datetime.now()
    head, details = G.lines(settings, now)
    head = head.replace("Still up", "Good morning") if now.hour < 5 else head
    out = [sleep_line(B.read_log(), now), *details, battery_line()]
    return head, [x for x in out if x]


def main(argv):
    mode = argv[1] if len(argv) > 1 else "text"
    settings = S.load()
    if mode == "show" and not settings["night"]["morning_summary"]:
        return 0
    head, details = lines(settings)
    if mode == "text":
        print("\n".join([head, *details]))
    elif mode == "show":
        sh.island("weather-clear-symbolic", head, 6)
        sh.notify(head, "\n".join(details) or "Have a good day.", "weather-clear-symbolic")
    else:
        print("usage: lennox-morning [text|show]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
