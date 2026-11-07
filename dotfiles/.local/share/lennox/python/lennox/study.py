"""Study buddy: a short recap when a focus session ends, and a line in your study notes.

    python3 -m lennox.study recap          the recap of today so far
    python3 -m lennox.study notes          where the notes file is, and its last lines
    python3 -m lennox.study end SUBJECT MINUTES   (focus mode calls this when a session ends)

The notes are plain text you can paste anywhere: ~/Documents/Study/notes.md.
"""

import os
import sys
import time

from . import focus as F
from . import settings as S
from . import sh

NOTES = os.path.expanduser("~/Documents/Study/notes.md")


def hours(minutes):
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def recap_lines(log, now, subject="", minutes=0):
    """Three lines: this session, today and the week, the streak with a suggestion."""
    st = F.stats(log, now)
    first = (f"{subject}: {hours(minutes)} done" if subject else f"{hours(minutes)} of focus done") if minutes else "Today so far"
    today = f"Today: {hours(st['today'])} in {st['sessions_today']} session{'s' if st['sessions_today'] != 1 else ''}  ·  this week: {hours(st['week'])}"
    by = [f"{k} {hours(v)}" for k, v in list(st["subjects"].items())[:3]]
    third = (f"Streak: {st['streak']} day{'s' if st['streak'] != 1 else ''}" if st["streak"] else "A streak starts with tomorrow")
    if by:
        third += "  ·  " + ", ".join(by)
    if st["sessions_today"] >= 4:
        third += "  ·  four sessions today: enough, rest your eyes"
    return [first, today, third]


def note_line(subject, minutes, when):
    return f"- {time.strftime('%H:%M', time.localtime(when))}  {subject or 'Focus'}  {hours(minutes)}"


def append_note(subject, minutes, when, path=None):
    """Adds the session under today's date heading (a new heading when the day changes)."""
    path = path or NOTES
    heading = f"## {time.strftime('%A %-d %B %Y', time.localtime(when))}"
    try:
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    except OSError:
        existing = "# Study notes\n"
    if heading not in existing:
        existing = existing.rstrip("\n") + f"\n\n{heading}\n"
    existing = existing.rstrip("\n") + "\n" + note_line(subject, minutes, when) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(existing)
    os.replace(path + ".tmp", path)


def session_ended(subject, minutes, now=None):
    """Called by focus mode: the notes line and the recap message."""
    now = now or time.time()
    if not S.load()["focus"]["notes"] or minutes < 1:
        return []
    lines = recap_lines(F._read(F.LOG, []), now, subject, minutes)
    append_note(subject, minutes, now - minutes * 60)
    sh.notify("Study recap", "\n".join(lines), "alarm-symbolic")
    return lines


def main(argv):
    mode = argv[1] if len(argv) > 1 else "recap"
    if mode == "recap":
        print("\n".join(recap_lines(F._read(F.LOG, []), time.time())))
    elif mode == "notes":
        print(NOTES)
        try:
            with open(NOTES, encoding="utf-8") as f:
                print("".join(f.readlines()[-12:]))
        except OSError:
            print("(no notes yet: they start with your next focus session)")
    elif mode == "end" and len(argv) > 3 and argv[3].isdigit():
        print("\n".join(session_ended(argv[2], int(argv[3]))))
    else:
        print("usage: lennox-study recap | notes | end SUBJECT MINUTES", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
