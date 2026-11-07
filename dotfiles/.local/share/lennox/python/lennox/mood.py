"""Mood diary and the weekly "why am I tired" report.

    python3 -m lennox.mood ask            asks how the day was (a notification with five faces)
    python3 -m lennox.mood set 1-5        saves today's mood
    python3 -m lennox.mood week           JSON: the last 7 days
    python3 -m lennox.mood report         tips from your own sleep, mood and focus

Everything stays on this laptop. The report needs about a week of notes before
it says anything about patterns.
"""

import datetime
import json
import os
import subprocess
import sys
import threading
import time

from . import bedtime as B
from . import focus as F
from . import settings as S
from . import sh

MOOD = os.path.join(S.STATE_DIR, "mood.json")
FACES = ["😞", "🙁", "😐", "🙂", "😄"]
WORDS = ["Rough", "Meh", "Okay", "Good", "Great"]


def load():
    try:
        with open(MOOD, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, int) and 1 <= v <= 5}
    except (OSError, ValueError, AttributeError):
        return {}


def save(data):
    os.makedirs(os.path.dirname(MOOD), exist_ok=True)
    with open(MOOD + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(MOOD + ".tmp", MOOD)


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now))


def set_today(score, now=None):
    data = load()
    data[today(now)] = int(score)
    keep = sorted(data)[-400:]
    save({k: data[k] for k in keep})


def week(data, now=None):
    now = time.time() if now is None else now
    days = [time.strftime("%Y-%m-%d", time.localtime(now - i * 86400)) for i in range(6, -1, -1)]
    return [{"day": d, "mood": data.get(d)} for d in days]


def _avg(values):
    return sum(values) / len(values) if values else None


def insights(moods, nights, focus_by_day, goal="23:30"):
    """Tips from your own data: [str]. `nights` is {night: 'HH:MM'} (when you stopped), as the sleep stats keep it."""
    tips = []
    if len(moods) < 5:
        return [f"Keep going: {len(moods)} of 5 days noted. After that Lennox can spot patterns."]
    # How a day went after a late night: the night's date is the evening before the mood's day
    late, normal = [], []
    usual = _avg([B.late(v) for v in nights.values()]) if nights else None
    for night, stop in nights.items():
        nxt = (datetime.date.fromisoformat(night) + datetime.timedelta(days=1)).isoformat()
        if nxt in moods and usual is not None:
            (late if B.late(stop) > usual + 45 else normal).append(moods[nxt])
    if len(late) >= 2 and len(normal) >= 2:
        diff = _avg(normal) - _avg(late)
        if diff >= 0.5:
            tips.append(f"Days after a late night feel {diff:.1f} points worse. Your usual is around {B.clock(round(usual))}; "
                        "staying near it protects your mood.")
        elif diff <= -0.5:
            tips.append("Late nights don't seem to hurt your mood. Watch your energy in class instead.")
    # Focus and mood
    busy = [m for d, m in moods.items() if focus_by_day.get(d, 0) >= 60]
    idle = [m for d, m in moods.items() if focus_by_day.get(d, 0) < 60]
    if len(busy) >= 2 and len(idle) >= 2 and _avg(busy) - _avg(idle) >= 0.5:
        tips.append(f"You feel better on days you focus for an hour or more ({_avg(busy):.1f} vs {_avg(idle):.1f}).")
    # Weekends
    wk = [m for d, m in moods.items() if datetime.date.fromisoformat(d).weekday() < 5]
    we = [m for d, m in moods.items() if datetime.date.fromisoformat(d).weekday() >= 5]
    if len(wk) >= 3 and len(we) >= 2 and abs(_avg(wk) - _avg(we)) >= 0.7:
        tips.append("Weekends feel " + ("better" if _avg(we) > _avg(wk) else "worse") + " than school days for you.")
    # Sleep versus the goal
    if nights and usual is not None and usual > B.late(goal) + 30:
        tips.append(f"You usually stop around {B.clock(round(usual))}, later than your {goal} goal. "
                    "Smart bedtime (Settings > Night) can move it earlier a little each week.")
    avg = _avg(list(moods.values()))
    tips.append(f"Your average mood over {len(moods)} days: {avg:.1f} of 5 ({WORDS[round(avg) - 1]}).")
    return tips


def report_text(now=None):
    focus_by_day = {}
    for x in F._read(F.LOG, []):
        d = time.strftime("%Y-%m-%d", time.localtime(x["start"]))
        focus_by_day[d] = focus_by_day.get(d, 0) + x["minutes"]
    return insights(load(), B.read_log(), focus_by_day, S.load()["night"]["bedtime_goal"])


def ask():
    """A notification with five faces; the tapped one is saved."""
    def run():
        try:
            out = subprocess.run(
                ["notify-send", "-a", "Lennox", "-i", "face-smile-symbolic", "-t", "60000", "--wait",
                 *[a for i, f in enumerate(FACES) for a in ("-A", f"{i + 1}={f} {WORDS[i]}")],
                 "How was today?", "One tap. It stays on this laptop."],
                capture_output=True, text=True, timeout=90, check=False).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return
        if out.isdigit() and 1 <= int(out) <= 5:
            set_today(out)
            sh.island("face-smile-symbolic", f"Noted: {WORDS[int(out) - 1]}", 3)
    thread = threading.Thread(target=run)
    thread.start()
    return thread


def main(argv):
    mode = argv[1] if len(argv) > 1 else "week"
    if mode == "ask":
        ask().join()
    elif mode == "set" and len(argv) > 2 and argv[2] in "12345" and len(argv[2]) == 1:
        set_today(argv[2])
    elif mode == "week":
        print(json.dumps(week(load())))
    elif mode == "report":
        print("\n".join(report_text()))
    else:
        print("usage: lennox-mood ask | set 1-5 | week | report", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
