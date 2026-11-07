"""Trophies for using Lennox: silly badges on a trophy page.

    python3 -m lennox.achievements list      JSON: every trophy, whether it is unlocked, how far along
    python3 -m lennox.achievements tick NAME count one use of a feature (used by Lennox's own tools)
    python3 -m lennox.achievements check     notify about trophies earned since last time

Everything is worked out from files that are already on this laptop.
"""

import json
import os
import sys
import time

from . import bedtime as B
from . import focus as F
from . import mood as M
from . import settings as S
from . import sh

COUNTS = os.path.join(S.STATE_DIR, "achievement-counts.json")
UNLOCKED = os.path.join(S.STATE_DIR, "achievements.json")
FIRST = os.path.join(S.STATE_DIR, "first-day")

# id, title, description, icon, (data key, goal)
TROPHIES = [
    ("first_focus", "First focus", "Finish a focus session", "find-location-symbolic", ("focus_sessions", 1)),
    ("focus_10h", "Deep worker", "Focus for 10 hours in total", "alarm-symbolic", ("focus_hours", 10)),
    ("focus_50h", "Mastermind", "Focus for 50 hours in total", "starred-symbolic", ("focus_hours", 50)),
    ("streak_3", "On a roll", "Focus 3 days in a row", "emblem-ok-symbolic", ("focus_streak", 3)),
    ("streak_7", "Unstoppable", "Focus 7 days in a row", "emblem-favorite-symbolic", ("focus_streak", 7)),
    ("night_owl", "Night owl", "Stay up past 2 AM five times", "weather-clear-night-symbolic", ("late_nights", 5)),
    ("early_bird", "Early bird", "Be done before 11 PM five nights", "weather-few-clouds-symbolic", ("early_nights", 5)),
    ("diary_7", "Dear diary", "Note your mood 7 days", "face-smile-symbolic", ("mood_days", 7)),
    ("veteran", "Veteran", "Use Lennox for 30 days", "user-home-symbolic", ("days_using", 30)),
    ("overview_100", "Window shopper", "Open the window overview 100 times", "view-grid-symbolic", ("overview", 100)),
    ("ocr_10", "Text thief", "Copy text from the screen 10 times", "edit-copy-symbolic", ("ocr", 10)),
    ("panic_1", "Close call", "Press the panic key once", "dialog-warning-symbolic", ("panic", 1)),
    ("ask_10", "Curious", "Ask Claude 10 questions", "help-about-symbolic", ("ask", 10)),
    ("snake_20", "Snake charmer", "Score 20 in Snake", "input-gaming-symbolic", ("snake_best", 20)),
]


def _json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def tick(name, amount=1, best=False):
    counts = _json(COUNTS, {})
    counts[name] = max(counts.get(name, 0), amount) if best else counts.get(name, 0) + amount
    _write(COUNTS, counts)


def days_using(now=None):
    now = time.time() if now is None else now
    try:
        with open(FIRST, encoding="utf-8") as f:
            first = float(f.read())
    except (OSError, ValueError):
        first = now
        os.makedirs(os.path.dirname(FIRST), exist_ok=True)
        with open(FIRST, "w", encoding="utf-8") as f:
            f.write(str(now))
    return int((now - first) // 86400)


def collect(now=None):
    now = time.time() if now is None else now
    log = F._read(F.LOG, [])
    nights = B.read_log()
    data = {"focus_sessions": len(log), "focus_hours": sum(x["minutes"] for x in log) // 60,
            "focus_streak": F.stats(log, now)["streak"],
            "late_nights": sum(1 for v in nights.values() if B.late("02:00") <= B.late(v) < B.late("06:00")),
            "early_nights": sum(1 for v in nights.values() if B.late(v) <= B.late("23:00")),
            "mood_days": len(M.load()), "days_using": days_using(now)}
    data.update(_json(COUNTS, {}))
    return data


def evaluate(data):
    out = []
    for tid, title, text, icon, (key, goal) in TROPHIES:
        have = data.get(key, 0)
        out.append({"id": tid, "title": title, "text": text, "icon": icon, "goal": goal,
                    "have": min(have, goal), "done": have >= goal})
    return out


def check():
    """Notifies about trophies earned since the last look; returns their titles."""
    known = set(_json(UNLOCKED, []))
    new = [t for t in evaluate(collect()) if t["done"] and t["id"] not in known]
    if new:
        _write(UNLOCKED, sorted(known | {t["id"] for t in new}))
        for t in new:
            sh.notify(f"Trophy: {t['title']}", t["text"], "starred-symbolic")
            sh.island("starred-symbolic", f"Trophy: {t['title']}", 5)
    return [t["title"] for t in new]


def main(argv):
    mode = argv[1] if len(argv) > 1 else "list"
    if mode == "list":
        print(json.dumps(evaluate(collect())))
    elif mode == "tick" and len(argv) > 2:
        if len(argv) > 3 and argv[3].isdigit():
            tick(argv[2], int(argv[3]), best=True)
        else:
            tick(argv[2])
    elif mode == "check":
        print("\n".join(check()) or "nothing new")
    else:
        print("usage: lennox-achieve list | tick NAME [BEST] | check", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
