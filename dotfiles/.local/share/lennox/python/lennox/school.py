"""School mode: deadlines, quiet hours, a school-day schedule.

    python3 -m lennox.school add TITLE DATE [HH:MM]   DATE: 2026-11-20, today, tomorrow, sun..sat, +3 (days)
    python3 -m lennox.school list [--json]            what is due, soonest first
    python3 -m lennox.school done ID | remove ID
    python3 -m lennox.school next                     one line: the next deadline
    python3 -m lennox.school quiet until HH:MM | for MINUTES | off | status
    python3 -m lennox.school study SUBJECT [MINUTES]  a focus session for that subject (Pomodoro rounds: Settings > Focus)
    python3 -m lennox.school watch                    (started at login) reminders and the school-hours schedule

"Quiet" is Do not disturb: notifications wait in the panel. With the school schedule on (Settings > School),
it turns itself on during school hours on school days (Jordan: Sunday to Thursday) and off afterwards.
Deadlines remind you a day and two hours before.
"""

import datetime
import fcntl
import json
import os
import re
import sys
import time

from . import settings as S
from . import sh

STATE = os.path.join(S.STATE_DIR, "school.json")
LOCK = os.path.join(S.RUNTIME_DIR, "school-watch.lock")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]          # datetime.weekday() order
REMIND = [("day", 24 * 3600), ("hours", 2 * 3600)]
KEEP_DONE = 14 * 86400


def load_state(path=None):
    try:
        with open(path or STATE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("deadlines", [])
    data.setdefault("next_id", 1)
    data.setdefault("quiet_until", 0)
    data.setdefault("dnd_by_us", False)
    return data


def save_state(data, path=None):
    path = path or STATE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


# ------------------------------------------------------------------ dates

def parse_time(text):
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", text.strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(f"'{text}' is not a time like 14:30")
    return int(m.group(1)), int(m.group(2))


def parse_due(date_text, time_text="23:59", now=None):
    """Epoch seconds for 'today', 'tomorrow', 'sun'..'sat' (next one), '+3' (days) or YYYY-MM-DD at HH:MM."""
    now_dt = datetime.datetime.fromtimestamp(now if now is not None else time.time())
    word = date_text.strip().lower()
    hour, minute = parse_time(time_text)
    if word == "today":
        day = now_dt.date()
    elif word == "tomorrow":
        day = now_dt.date() + datetime.timedelta(days=1)
    elif word[:3] in DAYS and len(word) <= 9:
        ahead = (DAYS.index(word[:3]) - now_dt.weekday()) % 7 or 7
        day = now_dt.date() + datetime.timedelta(days=ahead)
    elif re.fullmatch(r"\+\d{1,3}", word):
        day = now_dt.date() + datetime.timedelta(days=int(word[1:]))
    else:
        try:
            day = datetime.date.fromisoformat(word)
        except ValueError:
            raise ValueError(f"'{date_text}' is not a date: use 2026-11-20, today, tomorrow, sun..sat or +3") from None
    return datetime.datetime.combine(day, datetime.time(hour, minute)).timestamp()


def when_text(due, now):
    secs = due - now
    if secs < 0:
        return "overdue"
    if secs < 3600:
        return f"in {max(1, int(secs // 60))} min"
    if secs < 6 * 3600:
        return f"in {int(secs // 3600)} h"
    d_due = datetime.datetime.fromtimestamp(due).date()
    d_now = datetime.datetime.fromtimestamp(now).date()
    days = (d_due - d_now).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days ({DAYS[d_due.weekday()].capitalize()})" if days < 7 else d_due.isoformat()


# ------------------------------------------------------------------ deadlines

def add(state, title, due, now):
    item = {"id": state["next_id"], "title": title.strip(), "due": due, "done": False, "told": [], "added": now}
    state["next_id"] += 1
    state["deadlines"].append(item)
    return item


def open_items(state):
    return sorted((d for d in state["deadlines"] if not d["done"]), key=lambda d: d["due"])


def find(state, ident):
    return next((d for d in state["deadlines"] if str(d["id"]) == str(ident)), None)


def tidy(state, now):
    state["deadlines"] = [d for d in state["deadlines"] if not (d["done"] and now - d.get("done_at", now) > KEEP_DONE)]


def next_line(state, now):
    items = open_items(state)
    return f"{items[0]['title']} · {when_text(items[0]['due'], now)}" if items else ""


# ------------------------------------------------------------------ quiet (Do not disturb) and the schedule

def school_time(settings, now):
    """True during school hours on a school day."""
    if not S.get(settings, "school.schedule"):
        return False
    dt = datetime.datetime.fromtimestamp(now)
    days = {d.strip().lower()[:3] for d in str(S.get(settings, "school.days")).split(",")}
    if DAYS[dt.weekday()] not in days:
        return False
    try:
        start, end = parse_time(S.get(settings, "school.from")), parse_time(S.get(settings, "school.to"))
    except ValueError:
        return False
    return start <= (dt.hour, dt.minute) < end


def tick(state, settings, now, dnd, notify):
    """One round: reminders, quiet timer, school schedule. dnd(on) sets Do not disturb and returns True when it
    was already on before. Returns the new state."""
    for d in state["deadlines"]:
        if d["done"]:
            continue
        left = d["due"] - now
        if S.get(settings, "school.remind"):
            for key, secs in REMIND:
                if 0 < left <= secs and key not in d["told"]:
                    d["told"].append(key)
                    if not (key == "day" and left <= REMIND[1][1]):      # added late: only the closer reminder
                        notify(f"Deadline: {d['title']}", f"{d['title']} is due {when_text(d['due'], now)}.")
                        break
            if left <= 0 and "late" not in d["told"]:
                d["told"].append("late")
                notify("Deadline passed", f"{d['title']} was due. Mark it done when it is.")
    wanted_quiet = state["quiet_until"] > now
    scheduled = school_time(settings, now)
    if state["quiet_until"] and not wanted_quiet:
        state["quiet_until"] = 0
    if wanted_quiet or scheduled:
        if not state["dnd_by_us"]:
            if not dnd(True):                       # it was off: we turned it on, so we turn it off later
                state["dnd_by_us"] = True
    elif state["dnd_by_us"]:
        dnd(False)
        state["dnd_by_us"] = False
    tidy(state, now)
    return state


def swaync_dnd(on):
    before = sh.out(["swaync-client", "-D"], 3) == "true"
    sh.run(["swaync-client", "--dnd-on" if on else "--dnd-off", "--skip-wait"], 3)
    return before


def notify_cb(title, body):
    sh.notify(title, body, "appointment-soon")


def set_quiet(state, until, now):
    """Starts quiet until the epoch (0 = off). Applies it at once."""
    state["quiet_until"] = until
    tick(state, S.load(), now, swaync_dnd, notify_cb)
    return state


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    while True:
        try:
            state = tick(load_state(), S.load(), time.time(), swaync_dnd, notify_cb)
            save_state(state)
        except Exception as e:                      # one odd round must not stop the watcher
            print(f"lennox-school: {e}", file=sys.stderr)
        time.sleep(30)


# ------------------------------------------------------------------ command line

def main(argv):
    cmd = argv[1] if len(argv) > 1 else "list"
    args = [a for a in argv[2:] if not a.startswith("--")]
    now = time.time()
    state = load_state()
    try:
        if cmd == "add":
            if len(args) < 2:
                raise ValueError("usage: lennox-school add TITLE DATE [HH:MM]")
            title_words = args[:-2] if len(args) > 2 and re.fullmatch(r"\d{1,2}[:.]\d{2}", args[-1]) else args[:-1]
            if len(args) > 2 and re.fullmatch(r"\d{1,2}[:.]\d{2}", args[-1]):
                date_text, time_text = args[-2], args[-1]
            else:
                date_text, time_text = args[-1], "23:59"
            item = add(state, " ".join(title_words), parse_due(date_text, time_text, now), now)
            save_state(state)
            print(f"Added #{item['id']}: {item['title']} · {when_text(item['due'], now)}")
        elif cmd == "list":
            items = open_items(state)
            if "--json" in argv:
                print(json.dumps([{**d, "when": when_text(d["due"], now)} for d in items]))
            elif not items:
                print("Nothing due. 🎉")
            for d in ([] if "--json" in argv else items):
                print(f"  #{d['id']:<3} {d['title']:<34} {when_text(d['due'], now)}")
        elif cmd in ("done", "remove") and args:
            d = find(state, args[0])
            if not d:
                raise ValueError(f"No deadline #{args[0]}")
            if cmd == "done":
                d["done"], d["done_at"] = True, now
            else:
                state["deadlines"].remove(d)
            save_state(state)
            print(("Done: " if cmd == "done" else "Removed: ") + d["title"])
        elif cmd == "next":
            print(next_line(state, now))
        elif cmd == "quiet":
            sub = args[0] if args else "status"
            if sub == "until" and len(args) > 1:
                h, m = parse_time(args[1])
                at = datetime.datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0)
                if at.timestamp() <= now:
                    at += datetime.timedelta(days=1)
                state = set_quiet(state, at.timestamp(), now)
                print(f"Quiet until {args[1]}.")
            elif sub == "for" and len(args) > 1 and args[1].isdigit():
                state = set_quiet(state, now + int(args[1]) * 60, now)
                print(f"Quiet for {args[1]} min.")
            elif sub == "off":
                state = set_quiet(state, 0, now)
                print("Notifications are back.")
            else:
                until = state["quiet_until"]
                print(f"Quiet until {time.strftime('%H:%M', time.localtime(until))}." if until > now
                      else ("Quiet during school hours." if school_time(S.load(), now) else "Not quiet."))
            save_state(state)
        elif cmd == "study" and args:
            minutes = [a for a in args[1:] if a.isdigit()]
            sh.run([sh.bin_path("lennox-focus"), "start"] + minutes + [f"--subject={args[0]}"], 10)
            print(f"Focus session started for {args[0]}.")
        elif cmd == "watch":
            return watch()
        else:
            print("usage: lennox-school add|list|done|remove|next|quiet|study|watch", file=sys.stderr)
            return 2
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
