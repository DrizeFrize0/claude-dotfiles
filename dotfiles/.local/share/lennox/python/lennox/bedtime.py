"""Smart bedtime: learns when you really stop at night and suggests a bedtime
that works, then nudges it 15 minutes earlier each week you keep to it.

    python3 -m lennox.bedtime suggest [--json|--text]
    python3 -m lennox.bedtime apply        use the suggestion (the weekly run does this
                                          when Smart bedtime is on)

It reads the sleep stats (the last time you used the laptop each night,
~/.local/state/lennox/sleep.log), never more than the last 14 nights.
"""

import json
import os
import subprocess
import sys

from . import settings as S

SLEEP_LOG = os.path.join(S.STATE_DIR, "sleep.log")
NIGHTS = 14
MIN_NIGHTS = 5
SLACK = 20            # minutes after bedtime that still count as "on time"
STEP = 15             # how much earlier each good week


def late(hhmm):
    """'01:30' -> minutes after 18:00 (so 01:30 sorts after 23:30)."""
    h, m = (int(x) for x in hhmm.split(":"))
    minutes = h * 60 + m
    if minutes < 18 * 60:
        minutes += 24 * 60
    return minutes - 18 * 60


def clock(late_minutes):
    m = (late_minutes + 18 * 60) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def read_log(path=SLEEP_LOG):
    """{night: 'HH:MM'} (the latest time per night)."""
    nights = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and ":" in parts[1]:
                    nights[parts[0]] = parts[1]
    except OSError:
        pass
    return nights


def suggest(nights, bedtime, goal):
    """What bedtime to use next week, and why. All times 'HH:MM'."""
    recent = [late(nights[n]) for n in sorted(nights)[-NIGHTS:]]
    current, target = late(bedtime), late(goal)
    if len(recent) < MIN_NIGHTS:
        return {"kind": "learning", "nights": len(recent), "current": bedtime, "suggestion": bedtime,
                "text": f"Learning your nights: {len(recent)} of {MIN_NIGHTS} so far."}
    recent.sort()
    usual = recent[len(recent) // 2]                          # the median night
    out = {"nights": len(recent), "usual": clock(usual), "current": bedtime}
    if usual <= current + SLACK:
        if current > target:
            new = max(target, current - STEP)
            out.update(kind="earlier", suggestion=clock(new),
                       text=f"You stuck to {bedtime} (usually off by {clock(usual)}). Next step: {clock(new)}, "
                            f"on the way to {goal}.")
        else:
            out.update(kind="fits", suggestion=bedtime,
                       text=f"Your {bedtime} bedtime fits: you're usually off by {clock(usual)}.")
        return out
    realistic = max(target, (usual - 30) // STEP * STEP)       # a wind-down that starts before you stop
    if realistic <= current:
        out.update(kind="fits", suggestion=bedtime,
                   text=f"You usually stop around {clock(usual)}, a bit after your {bedtime} bedtime.")
        return out
    out.update(kind="later", suggestion=clock(realistic),
               text=f"You usually stop around {clock(usual)}, so a {bedtime} wind-down comes too early to "
                    f"help. Starting it at {clock(realistic)} catches you, then it moves 15 minutes "
                    f"earlier each week you keep to it, until {goal}.")
    return out


def current():
    night = S.load()["night"]
    return suggest(read_log(), night["winddown_time"], night["bedtime_goal"])


def apply(result):
    if result["suggestion"] == result["current"] or result["kind"] == "learning":
        return False
    subprocess.run([os.path.expanduser("~/.local/bin/lennox-set"), "night.winddown_time", result["suggestion"]],
                   capture_output=True, check=False)
    return True


def main(argv):
    mode = argv[1] if len(argv) > 1 else "suggest"
    result = current()
    if mode == "suggest":
        print(json.dumps(result) if "--json" in argv else result["text"])
    elif mode == "apply":
        if apply(result):
            print(f"Bedtime is now {result['suggestion']}. {result['text']}")
    else:
        print("usage: lennox-bedtime suggest [--json|--text] | apply", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
