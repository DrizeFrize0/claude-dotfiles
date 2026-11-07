"""Dynamic wallpaper: the picture follows the time of day and the weather.

    python3 -m lennox.dynwall check [--force]     change the wallpaper if the time of day or the weather moved on

Uses the Lennox wallpaper pack (Settings > Wallpaper > paint it). Dawn, day, evening and night each have their own
pictures; rain or a storm brings a moody one. The same day always gives the same picture for the same situation.
"""

import datetime
import json
import os
import sys

from . import settings as S
from . import sh

STATE = os.path.join(S.STATE_DIR, "dynwall.json")
PACK = os.path.expanduser("~/.config/lennox/wallpapers/lennox")
SLOTS = {
    "dawn": ("mesh-peach", "mountains-dusk", "ocean-layers"),
    "day": ("clouds", "dunes", "mesh-mint", "ocean-layers", "forest-mist"),
    "evening": ("sunset-beach", "mountains-dusk", "mesh-peach", "dunes"),
    "night": ("night-owl", "aurora", "mesh-lavender", "graphite"),
}
MOODY = ("forest-mist", "graphite", "mountains-dusk", "clouds")
RAIN_WORDS = ("rain", "shower", "drizzle", "storm", "thunder", "snow")


def slot_of(hour):
    if 5 <= hour < 8:
        return "dawn"
    if 8 <= hour < 17:
        return "day"
    if 17 <= hour < 20:
        return "evening"
    return "night"


def choose(hour, weather_text, day_number, available):
    """The wallpaper key for this situation (None if the pack has none of its candidates)."""
    wet = any(w in (weather_text or "").lower() for w in RAIN_WORDS)
    candidates = [k for k in (MOODY if wet and slot_of(hour) != "night" else SLOTS[slot_of(hour)]) if k in available]
    if not candidates:
        candidates = [k for k in SLOTS[slot_of(hour)] if k in available]
    return candidates[day_number % len(candidates)] if candidates else None


def available(pack=PACK):
    try:
        return {f[len("lennox-"):-len(".jpg")] for f in os.listdir(pack) if f.startswith("lennox-") and f.endswith(".jpg")}
    except OSError:
        return set()


def weather_text():
    try:
        from .widgets import data as D
        w = (D._read_cache().get("forecast") or {}).get("data") or {}
        return w.get("text", "")
    except Exception:  # noqa: BLE001  no weather is fine: just the time of day
        return ""


def check(now=None, force=False, pack=PACK, weather=None, apply=None):
    now = now or datetime.datetime.now()
    keys = available(pack)
    key = choose(now.hour, weather_text() if weather is None else weather, now.timetuple().tm_yday, keys)
    if key is None:
        return None
    try:
        with open(STATE, encoding="utf-8") as f:
            last = json.load(f).get("key")
    except (OSError, ValueError, AttributeError):
        last = None
    if key == last and not force:
        return None
    path = os.path.join(pack, f"lennox-{key}.jpg")
    (apply or (lambda p: sh.run([sh.bin_path("lennox-wallpaper"), p, "--quiet"], 120)))(path)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"key": key}, f)
    return key


def main(argv):
    if (argv[1] if len(argv) > 1 else "check") != "check":
        print("usage: lennox-dynwall check [--force]", file=sys.stderr)
        return 2
    print(check(force="--force" in argv) or "no change")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
