"""Theme of the season: colors (and a wallpaper, if you add some) for the occasions you pick.

    python3 -m lennox.seasons check        apply or undo for today
    python3 -m lennox.seasons today        what today is

Ramadan and Eid use the tabular Islamic calendar, which can differ from the
moon sighting by a day. Put pictures in ~/.config/lennox/seasons/NAME/ (NAME
= ramadan, eid, halloween, newyear, jordan_day) for a wallpaper too.
"""

import datetime
import glob
import json
import os
import random
import sys

from . import settings as S
from . import sh

STATE = os.path.join(S.STATE_DIR, "season.json")
THEME = {"ramadan": "gold", "eid": "forest", "halloween": "sunset", "newyear": "lavender", "jordan_day": "crimson"}
LABEL = {"ramadan": "Ramadan", "eid": "Eid", "halloween": "Halloween", "newyear": "New Year", "jordan_day": "Independence Day"}


def hijri(day):
    """(year, month, day) of the tabular Islamic calendar for a date."""
    jd = day.toordinal() + 1721425
    l = jd - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
    l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    month = (24 * l) // 709
    return 30 * n + j - 30, month, l - (709 * month) // 24


def occasions(day):
    """The occasions that are on for a date: ['ramadan', ...]."""
    _y, m, d = hijri(day)
    found = []
    if m == 9:
        found.append("ramadan")
    if (m == 10 and d <= 3) or (m == 12 and 10 <= d <= 13):
        found.append("eid")
    if day.month == 10 and day.day >= 25:
        found.append("halloween")
    if (day.month == 12 and day.day >= 30) or (day.month == 1 and day.day <= 2):
        found.append("newyear")
    if day.month == 5 and 24 <= day.day <= 26:
        found.append("jordan_day")
    return found


def pick(day, wanted):
    """The occasion to show (first wanted one that is on), or None."""
    for name in occasions(day):
        if wanted.get(name):
            return name
    return None


def _state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(state):
    if state is None:
        try:
            os.remove(STATE)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def check(day=None):
    day = day or datetime.date.today()
    settings = S.load()
    wanted = settings["seasons"] if settings["seasons"]["on"] else {}
    name = pick(day, wanted)
    state = _state()
    if name == (state or {}).get("name"):
        return None
    if state:                                           # the occasion ended: back to what you had
        S.set_value("appearance.theme", state["theme_before"])
        sh.run([sh.bin_path("lennox-apply"), "theme"], 60)
        _save(None)
    if name:
        _save({"name": name, "theme_before": settings["appearance"]["theme"]})
        S.set_value("appearance.theme", THEME[name])
        sh.run([sh.bin_path("lennox-apply"), "theme"], 60)
        pictures = sorted(glob.glob(os.path.join(S.CONFIG_DIR, "seasons", name, "*.*")))
        if pictures:
            sh.run([sh.bin_path("lennox-wallpaper"), random.choice(pictures), "--quiet"], 60)
        sh.island("weather-clear-symbolic", f"{LABEL[name]} theme", 5)
    return name or "ended"


def main(argv):
    mode = argv[1] if len(argv) > 1 else "today"
    if mode == "check":
        print(check() or "nothing to do")
    elif mode == "today":
        day = datetime.date.today()
        print(", ".join(LABEL[o] for o in occasions(day)) or "No occasion today", "| Hijri", "{}-{:02d}-{:02d}".format(*hijri(day)))
    else:
        print("usage: lennox-seasons check | today", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
