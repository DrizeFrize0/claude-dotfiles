"""Timers, alarms, reminders and the stopwatch.

Everything lives in ~/.local/state/lennox/clock.json. The Clock app and
`lennox-clock` change it; the widgets process (always running) watches it,
fires what is due, rings, and shows it in the dynamic island. Plain Python,
no GTK, so it can be tested on its own.

    lennox-clock timer 20m [label]          lennox-clock remind 18:00 Check the server
    lennox-clock alarm 07:30 [label] [--days mon,tue,...|weekdays|daily]
    lennox-clock stopwatch start|stop|lap|reset
    lennox-clock list | cancel ID | stop | snooze [minutes]
"""

import contextlib
import datetime
import fcntl
import json
import os
import re
import sys
import time
import uuid

STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "lennox")
CLOCK_FILE = os.path.join(STATE_DIR, "clock.json")
SNOOZE_MINUTES = 10
MISSED_AFTER = 10 * 60       # due more than 10 minutes ago (laptop was off): just tell, don't ring
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def empty():
    return {"timers": [], "alarms": [], "reminders": [], "ringing": [],
            "stopwatch": {"start": None, "elapsed": 0.0, "laps": []},
            "world": ["Europe/London", "America/New_York", "Asia/Tokyo"]}


# ---------------------------------------------------------------- storage

@contextlib.contextmanager
def edit(path=None):
    """Read, change and save clock.json under a lock: `with edit() as data: ...`"""
    path = path or CLOCK_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load(path)
        yield data
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)


def load(path=None):
    data = empty()
    try:
        with open(path or CLOCK_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            for key, value in saved.items():
                if key in data and isinstance(value, type(data[key])):
                    data[key] = value
    except (OSError, ValueError):
        pass
    return data


def new_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------- parsing

def parse_duration(text):
    """'20m', '1h30m', '90s', '1:30' (h:mm), '25' (minutes) -> seconds, or None."""
    text = text.strip().lower().replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(float(text) * 60) or None
    m = re.fullmatch(r"(\d+):(\d{2})", text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    parts = re.findall(r"(\d+(?:\.\d+)?)(h|m|min|s|sec)", text)
    if not parts or "".join(n + u for n, u in parts) != text:
        return None
    unit = {"h": 3600, "m": 60, "min": 60, "s": 1, "sec": 1}
    total = int(sum(float(n) * unit[u] for n, u in parts))
    return total if total > 0 else None


def parse_time(text):
    """'18:00', '7:30', '7pm', '7:30am' -> (hour, minute), or None."""
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text.strip().lower())
    if not m:
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "pm" else 0)
    elif m.group(2) is None:
        return None          # a bare "7" is ambiguous: say 7:00 or 7am
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def parse_days(text):
    """'weekdays', 'weekends', 'daily', 'mon,wed,fri' -> list of weekday numbers (0 = Monday)."""
    text = (text or "").strip().lower()
    if not text or text == "once":
        return []
    named = {"daily": list(range(7)), "everyday": list(range(7)), "weekdays": [0, 1, 2, 3, 4],
             "weekends": [5, 6], "weekend": [5, 6]}
    if text in named:
        return named[text]
    days = []
    for part in text.split(","):
        part = part.strip()[:3]
        if part not in DAY_NAMES:
            raise ValueError(f"unknown day '{part}' (use mon, tue, wed, thu, fri, sat, sun)")
        days.append(DAY_NAMES.index(part))
    return sorted(set(days))


def next_time(hour, minute, days, now):
    """The next moment at hour:minute (on one of `days`, or any day if empty) after `now`."""
    base = datetime.datetime.fromtimestamp(now).replace(hour=hour, minute=minute, second=0, microsecond=0)
    for offset in range(8):
        candidate = base + datetime.timedelta(days=offset)
        if candidate.timestamp() > now and (not days or candidate.weekday() in days):
            return candidate.timestamp()
    return None


def when(text, now):
    """A reminder time: a clock time ('18:00', '7pm') or a duration ('20m', '1h') -> epoch.
    With a colon or am/pm it is always a time of day, so '18:00' never means 18 hours."""
    hm = parse_time(text)
    if hm:
        return next_time(hm[0], hm[1], [], now)
    if ":" in text:
        return None
    seconds = parse_duration(text)
    return now + seconds if seconds else None


# ---------------------------------------------------------------- changes

def add_timer(data, seconds, label, now):
    timer = {"id": new_id("t"), "label": label or "Timer", "duration": seconds, "end": now + seconds,
             "paused_left": None}
    data["timers"].append(timer)
    return timer


def pause_timer(data, timer_id, now):
    for t in data["timers"]:
        if t["id"] == timer_id:
            if t.get("paused_left") is None:
                t["paused_left"] = max(0.0, t["end"] - now)
            else:
                t["end"] = now + t["paused_left"]
                t["paused_left"] = None
            return t
    return None


def add_alarm(data, hour, minute, label, days, now):
    alarm = {"id": new_id("a"), "time": f"{hour:02d}:{minute:02d}", "label": label or "Alarm",
             "days": days, "enabled": True, "next": next_time(hour, minute, days, now)}
    data["alarms"].append(alarm)
    return alarm


def set_alarm_enabled(data, alarm_id, enabled, now):
    for a in data["alarms"]:
        if a["id"] == alarm_id:
            a["enabled"] = enabled
            hour, minute = (int(x) for x in a["time"].split(":"))
            a["next"] = next_time(hour, minute, a["days"], now) if enabled else None
            return a
    return None


def add_reminder(data, at, text):
    reminder = {"id": new_id("r"), "at": at, "text": text or "Reminder"}
    data["reminders"].append(reminder)
    return reminder


def cancel(data, item_id):
    for key in ("timers", "alarms", "reminders", "ringing"):
        before = len(data[key])
        data[key] = [x for x in data[key] if x.get("id") != item_id]
        if len(data[key]) != before:
            return True
    return False


def stopwatch(data, action, now):
    sw = data["stopwatch"]
    if action == "start" and sw["start"] is None:
        sw["start"] = now
    elif action == "stop" and sw["start"] is not None:
        sw["elapsed"] += now - sw["start"]
        sw["start"] = None
    elif action == "lap":
        sw["laps"].append(stopwatch_elapsed(sw, now))
    elif action == "reset":
        data["stopwatch"] = {"start": None, "elapsed": 0.0, "laps": []}
    return data["stopwatch"]


def stopwatch_elapsed(sw, now):
    return sw["elapsed"] + (now - sw["start"] if sw["start"] is not None else 0)


def stop_ringing(data):
    stopped = data["ringing"]
    data["ringing"] = []
    return stopped


def snooze(data, now, minutes=SNOOZE_MINUTES):
    """Ringing things come back in a few minutes (as a timer, so it shows a countdown)."""
    snoozed = []
    for item in stop_ringing(data):
        snoozed.append(add_timer(data, minutes * 60, f"{item['label']} (snoozed)", now))
    return snoozed


# ---------------------------------------------------------------- what is due

def due(data, now):
    """Take everything that is due out of `data`. Returns [(kind, item, missed)].

    Timers and reminders are removed, alarms move to their next day (or turn
    off if they don't repeat). `missed` means it was due long ago (the laptop
    was off): tell, don't ring.
    """
    fired = []
    keep = []
    for t in data["timers"]:
        if t.get("paused_left") is None and t["end"] <= now:
            fired.append(("timer", t, now - t["end"] > MISSED_AFTER))
        else:
            keep.append(t)
    data["timers"] = keep
    keep = []
    for r in data["reminders"]:
        if r["at"] <= now:
            fired.append(("reminder", r, now - r["at"] > MISSED_AFTER))
        else:
            keep.append(r)
    data["reminders"] = keep
    for a in data["alarms"]:
        if a.get("enabled") and a.get("next") and a["next"] <= now:
            fired.append(("alarm", dict(a), now - a["next"] > MISSED_AFTER))
            hour, minute = (int(x) for x in a["time"].split(":"))
            if a["days"]:
                a["next"] = next_time(hour, minute, a["days"], now)
            else:
                a["enabled"], a["next"] = False, None
    for kind, item, missed in fired:
        if kind in ("timer", "alarm") and not missed:
            data["ringing"].append({"id": item["id"], "kind": kind, "label": item["label"], "since": now})
    return fired


def next_up(data, now):
    """The soonest running timer, alarm or reminder: (kind, item, seconds left) or None."""
    upcoming = []
    for t in data["timers"]:
        left = t["paused_left"] if t.get("paused_left") is not None else t["end"] - now
        upcoming.append((left, "timer", t))
    for a in data["alarms"]:
        if a.get("enabled") and a.get("next"):
            upcoming.append((a["next"] - now, "alarm", a))
    for r in data["reminders"]:
        upcoming.append((r["at"] - now, "reminder", r))
    if not upcoming:
        return None
    left, kind, item = min(upcoming, key=lambda x: x[0])
    return kind, item, max(0.0, left)


# ---------------------------------------------------------------- text

def countdown(seconds):
    seconds = int(round(max(0, seconds)))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def short_left(seconds):
    """'45s', '12m', '3h 05m', '2d' for the bar."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{(seconds + 59) // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"
    return f"{seconds // 86400}d"


def days_text(days):
    if not days:
        return "Once"
    if days == list(range(7)):
        return "Every day"
    if days == [0, 1, 2, 3, 4]:
        return "Weekdays"
    if days == [5, 6]:
        return "Weekends"
    return ", ".join(DAY_NAMES[d].capitalize() for d in days)


def waybar(data, now):
    sw = data["stopwatch"]
    up = next_up(data, now)
    if data["ringing"]:
        item = data["ringing"][0]
        return {"text": f"󰀠 {item['label']}", "class": "ringing",
                "tooltip": "Ringing: click to open the Clock (lennox-clock stop)"}
    if up and (up[0] == "timer" or up[2] < 12 * 3600):
        kind, item, left = up
        icon = {"timer": "󰔛", "alarm": "󰀠", "reminder": "󰃰"}[kind]
        paused = kind == "timer" and item.get("paused_left") is not None
        label = item.get("label") or item.get("text", "")
        text = f"{icon} {short_left(left)}" + (" ⏸" if paused else "")
        return {"text": text, "class": kind, "tooltip": f"{label}: {countdown(left)} left\nClick to open the Clock"}
    if sw["start"] is not None:
        return {"text": f"󱎫 {countdown(stopwatch_elapsed(sw, now))}", "class": "stopwatch",
                "tooltip": "Stopwatch running"}
    return {"text": ""}


# ---------------------------------------------------------------- command line

def _usage():
    print(__doc__.split("\n\n", 2)[2].rstrip(), file=sys.stderr)
    return 2


def main(argv, now=None, path=None):
    now = now or time.time()
    args = argv[1:]
    if not args:
        return _usage()
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "timer":
            seconds = parse_duration(rest[0]) if rest else None
            if not seconds:
                print("lennox-clock timer DURATION [label]   (like 20m, 1h30m, 90s)", file=sys.stderr)
                return 2
            with edit(path) as data:
                t = add_timer(data, seconds, " ".join(rest[1:]), now)
            print(f"Timer {t['label']}: {countdown(seconds)} ({t['id']})")
        elif cmd == "remind":
            at = when(rest[0], now) if rest else None
            if not at:
                print("lennox-clock remind WHEN TEXT   (WHEN: 20m, 1h, 18:00, 7pm)", file=sys.stderr)
                return 2
            with edit(path) as data:
                r = add_reminder(data, at, " ".join(rest[1:]))
            print(f"Reminder at {datetime.datetime.fromtimestamp(at):%H:%M}: {r['text']} ({r['id']})")
        elif cmd == "alarm":
            days = []
            if "--days" in rest:
                i = rest.index("--days")
                days = parse_days(rest[i + 1] if i + 1 < len(rest) else "")
                rest = rest[:i] + rest[i + 2:]
            hm = parse_time(rest[0]) if rest else None
            if not hm:
                print("lennox-clock alarm HH:MM [label] [--days weekdays|daily|mon,wed]", file=sys.stderr)
                return 2
            with edit(path) as data:
                a = add_alarm(data, hm[0], hm[1], " ".join(rest[1:]), days, now)
            print(f"Alarm {a['time']} ({days_text(days)}): {a['label']} ({a['id']})")
        elif cmd == "stopwatch":
            action = rest[0] if rest else "start"
            if action not in ("start", "stop", "lap", "reset"):
                return _usage()
            with edit(path) as data:
                sw = stopwatch(data, action, now)
            print(f"Stopwatch {action}: {countdown(stopwatch_elapsed(sw, now))}")
        elif cmd == "cancel":
            with edit(path) as data:
                ok = bool(rest) and cancel(data, rest[0])
            if not ok:
                print("Nothing with that id (see: lennox-clock list)", file=sys.stderr)
                return 1
        elif cmd == "stop":
            with edit(path) as data:
                stop_ringing(data)
        elif cmd == "snooze":
            minutes = int(rest[0]) if rest else SNOOZE_MINUTES
            with edit(path) as data:
                snooze(data, now, minutes)
        elif cmd == "list":
            data = load(path)
            for t in data["timers"]:
                left = t["paused_left"] if t.get("paused_left") is not None else t["end"] - now
                print(f"{t['id']}  timer     {countdown(left)} left  {t['label']}")
            for a in data["alarms"]:
                state = "on " if a.get("enabled") else "off"
                print(f"{a['id']}  alarm {state} {a['time']} {days_text(a['days'])}  {a['label']}")
            for r in data["reminders"]:
                print(f"{r['id']}  reminder  {datetime.datetime.fromtimestamp(r['at']):%a %H:%M}  {r['text']}")
        elif cmd == "waybar":
            print(json.dumps(waybar(load(path), now), ensure_ascii=False))
        else:
            return _usage()
    except (ValueError, IndexError) as e:
        print(f"lennox-clock: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
