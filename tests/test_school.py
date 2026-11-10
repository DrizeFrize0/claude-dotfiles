"""School mode. Run: python3 tests/test_school.py"""
import datetime
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_STATE_HOME=os.path.join(T, "state"), XDG_CONFIG_HOME=os.path.join(T, "cfg"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import school as C  # noqa: E402
from lennox import settings as S  # noqa: E402

fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    c or fails.append(what)


def at(y, m, d, hh=0, mm=0):
    return datetime.datetime(y, m, d, hh, mm).timestamp()


NOW = at(2026, 11, 11, 10, 0)            # a Wednesday
check(datetime.date(2026, 11, 11).weekday() == 2, "2026-11-11 is a Wednesday (test sanity)")
check(C.parse_due("tomorrow", "08:00", NOW) == at(2026, 11, 12, 8), "tomorrow")
check(C.parse_due("today", now=NOW) == at(2026, 11, 11, 23, 59), "today defaults to end of day")
check(C.parse_due("sun", "07:30", NOW) == at(2026, 11, 15, 7, 30), "next sunday")
check(C.parse_due("wed", now=NOW) == at(2026, 11, 18, 23, 59), "'wed' on a wednesday means next week")
check(C.parse_due("+3", now=NOW) == at(2026, 11, 14, 23, 59) and C.parse_due("2026-12-01", "9:05", NOW) == at(2026, 12, 1, 9, 5),
      "+3 days and a full date")
for bad in (("someday", "10:00"), ("tomorrow", "25:00")):
    try:
        C.parse_due(*bad, now=NOW)
        check(False, f"{bad} is rejected")
    except ValueError:
        check(True, f"{bad} is rejected")
check(C.when_text(NOW - 5, NOW) == "overdue" and C.when_text(NOW + 1800, NOW) == "in 30 min"
      and C.when_text(at(2026, 11, 11, 20), NOW) == "today" and C.when_text(at(2026, 11, 12, 9), NOW) == "tomorrow"
      and C.when_text(at(2026, 11, 14, 9), NOW) == "in 3 days (Sat)", "when_text")

s = C.load_state()
a = C.add(s, "Chemistry report", at(2026, 11, 12, 8), NOW)
b = C.add(s, "Math quiz", at(2026, 11, 11, 15), NOW)
check([d["title"] for d in C.open_items(s)] == ["Math quiz", "Chemistry report"], "soonest first")
check(C.next_line(s, NOW) == "Math quiz · in 5 h", "next line")
C.save_state(s)
check(C.load_state()["next_id"] == 3, "state round-trips")

# reminders
sent, dnd_calls = [], []
cfg = {"school": {"remind": True, "schedule": False, "days": "sun, mon, tue, wed, thu", "from": "07:30", "to": "14:30"}}


def dnd(on):
    dnd_calls.append(on)
    return False


note = lambda t, b: sent.append(t)  # noqa: E731
C.tick(s, cfg, at(2026, 11, 11, 9, 0), dnd, note)      # math quiz in 6h, chem in 23h
check(sent == ["Deadline: Chemistry report", "Deadline: Math quiz"], "within a day: both get a reminder")
C.tick(s, cfg, at(2026, 11, 11, 9, 5), dnd, note)
check(len(sent) == 2, "told once")
C.tick(s, cfg, at(2026, 11, 11, 13, 30), dnd, note)    # math quiz in 90 min
check("Deadline: Math quiz" in sent, "two hours before")
C.tick(s, cfg, at(2026, 11, 11, 16, 0), dnd, note)
check("Deadline passed" in sent, "after it passes")
s2 = {"deadlines": [], "next_id": 1, "quiet_until": 0, "dnd_by_us": False}
C.add(s2, "Late add", at(2026, 11, 11, 11, 0), NOW)
n = len(sent)
C.tick(s2, cfg, at(2026, 11, 11, 10, 30), dnd, note)
check(len(sent) == n + 1 and sent[-1] == "Deadline: Late add", "added close to the deadline: one reminder, not two")

# quiet timer and school schedule
state = C.load_state()
state["quiet_until"] = NOW + 600
C.tick(state, cfg, NOW, dnd, note)
check(dnd_calls == [True] and state["dnd_by_us"], "quiet turns Do not disturb on")
C.tick(state, cfg, NOW + 700, dnd, note)
check(dnd_calls == [True, False] and not state["dnd_by_us"] and state["quiet_until"] == 0, "and off when the time is up")

dnd_calls.clear()
cfg["school"]["schedule"] = True
state = C.load_state()
C.tick(state, cfg, at(2026, 11, 11, 9, 0), dnd, note)
check(dnd_calls == [True], "school hours on a school day: quiet")
C.tick(state, cfg, at(2026, 11, 11, 14, 31), dnd, note)
check(dnd_calls == [True, False], "school over: back")
C.tick(state, cfg, at(2026, 11, 13, 9, 0), dnd, note)          # Friday
check(dnd_calls == [True, False], "Friday is not a school day")
dnd_calls.clear()
state = C.load_state()
C.tick(state, cfg, at(2026, 11, 11, 9, 0), lambda on: (dnd_calls.append(on) or True), note)
C.tick(state, cfg, at(2026, 11, 11, 15, 0), lambda on: (dnd_calls.append(on) or True), note)
check(dnd_calls == [True] and not state["dnd_by_us"], "if Do not disturb was already on, it is left on")

# done items get cleaned up after two weeks
state = C.load_state()
d = C.add(state, "old", NOW, NOW)
d["done"], d["done_at"] = True, NOW - 20 * 86400
C.tidy(state, NOW)
check(all(x["title"] != "old" for x in state["deadlines"]), "old finished deadlines are dropped")
check(S.get(S.load(), "school.days").startswith("sun"), "default school week is Sunday to Thursday")
print("OK school" if not fails else "FAILED school: %d" % len(fails))
sys.exit(1 if fails else 0)
