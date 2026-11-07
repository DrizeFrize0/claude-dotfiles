"""Wallpaper of the day: a fresh wallpaper each morning, from a folder you choose.

    python3 -m lennox.wotd [today]    set today's wallpaper now

The same day always gives the same picture, and the pictures take turns through the
folder (the Lennox wallpapers unless you pick another in Settings > Wallpaper).
"""

import datetime
import os
import sys

from . import settings as S
from . import sh

EXT = (".jpg", ".jpeg", ".png", ".webp")


def folder(settings):
    custom = os.path.expanduser(settings["wallpaper"]["daily_folder"])
    if custom:
        return custom
    base = os.path.expanduser(settings["wallpaper"].get("folder", ""))
    return base or os.path.expanduser("~/.config/lennox/wallpapers")


def pictures(path):
    found = []
    for root, _dirs, names in os.walk(path):
        found += [os.path.join(root, n) for n in names if n.lower().endswith(EXT) and not n.startswith("live-frame")]
        if len(found) > 3000:
            break
    return sorted(found)


def pick(files, day):
    """Today's picture: days count through the folder in turn."""
    return files[day.toordinal() % len(files)] if files else None


def apply(day=None):
    day = day or datetime.date.today()
    choice = pick(pictures(folder(S.load())), day)
    if not choice:
        return None
    sh.run([sh.bin_path("lennox-wallpaper"), choice, "--quiet"], 90)
    return choice


def main(argv):
    if (argv[1] if len(argv) > 1 else "today") != "today":
        print("usage: python3 -m lennox.wotd [today]", file=sys.stderr)
        return 2
    print(apply() or "No pictures in the folder")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
