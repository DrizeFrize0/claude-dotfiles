"""Versions and "What's new" after an upgrade.

    python3 -m lennox.whatsnew version          this Lennox's version
    python3 -m lennox.whatsnew show [--since V] the changes (all, or newer than V)
    python3 -m lennox.whatsnew check            once per new version: a notification
    python3 -m lennox.whatsnew seen             don't notify about this version

The changes live in ~/.local/share/lennox/CHANGELOG.md.
"""

import os
import re
import subprocess
import sys

from . import VERSION
from . import settings as S

# ~/.local/share/lennox/python/lennox/whatsnew.py -> ~/.local/share/lennox/CHANGELOG.md
CHANGELOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "CHANGELOG.md")
SEEN = os.path.join(S.STATE_DIR, "seen_version")
HEADING = re.compile(r"^## (\d+\.\d+\.\d+)(?: · ([\d-]+))?(?: · (.+))?\s*$")


def key(version):
    """'1.4.0' -> (1, 4, 0); None if it isn't a version (an old git hash, say)."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (version or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def parse(text):
    """[{'version', 'date', 'title', 'items'}], newest first as written."""
    entries, current = [], None
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            current = {"version": m.group(1), "date": m.group(2) or "", "title": m.group(3) or "", "items": []}
            entries.append(current)
        elif current is not None and line.startswith("- "):
            current["items"].append(line[2:].strip())
    return entries


def load(path=CHANGELOG):
    try:
        with open(path, encoding="utf-8") as f:
            return parse(f.read())
    except OSError:
        return []


def newer_than(entries, version):
    """Entries newer than `version` (just the latest one if `version` can't be read)."""
    old = key(version)
    if old is None:
        return entries[:1]
    return [e for e in entries if key(e["version"]) and key(e["version"]) > old]


def read_seen(path=SEEN):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def mark_seen(version=VERSION, path=SEEN):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(version + "\n")
    os.replace(path + ".tmp", path)


def text(entries):
    out = []
    for e in entries:
        out.append(f"Lennox {e['version']}" + (f" · {e['title']}" if e["title"] else "")
                   + (f" ({e['date']})" if e["date"] else ""))
        out += [f"  • {item}" for item in e["items"]]
        out.append("")
    return "\n".join(out).rstrip()


def check():
    """Notify once about what's new since the last version you saw."""
    seen = read_seen()
    if seen is not None and key(seen) and key(seen) >= key(VERSION):
        return False
    entries = newer_than(load(), seen)
    if not entries:
        mark_seen()
        return False
    highlights = [item for e in entries for item in e["items"]][:4]
    body = "\n".join(f"• {item}" for item in highlights)
    mark_seen()                     # before waiting on the click, so it's shown once
    try:
        choice = subprocess.run(
            ["notify-send", "-a", "Lennox", "-i", "software-update-available", "-t", "20000",
             "-A", "open=See everything new", f"Lennox updated to {VERSION}", body],
            capture_output=True, text=True, timeout=60, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return True
    if choice == "open":
        subprocess.Popen(["setsid", "-f", os.path.expanduser("~/.local/bin/lennox-settings"), "--page", "about"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def main(argv):
    mode = argv[1] if len(argv) > 1 else "show"
    if mode == "version":
        print(VERSION)
    elif mode == "show":
        entries = load()
        if "--since" in argv:
            i = argv.index("--since")
            entries = newer_than(entries, argv[i + 1] if i + 1 < len(argv) else "")
        print(text(entries) if entries else "Nothing new.")
    elif mode == "check":
        check()
    elif mode == "seen":
        mark_seen()
    else:
        print("usage: lennox-whatsnew version | show [--since VERSION] | check | seen", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
