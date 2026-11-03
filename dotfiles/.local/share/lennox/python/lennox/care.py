"""Daily care: a water reminder, heat alerts and prayer times.

    python3 -m lennox.care watch          (started at login) does all three, quietly
    python3 -m lennox.care prayer [--json]   today's prayer times and the next one
    python3 -m lennox.care heat           the temperatures right now

Each part has its own switch in Lennox Settings > Daily care. Nothing here
uses the network, and nothing wakes the NVIDIA chip just to read its heat.
"""

import datetime
import fcntl
import glob
import json
import math
import os
import subprocess
import sys
import threading
import time

from . import settings as S
from . import sh

LOCK = os.path.join(S.RUNTIME_DIR, "care-watch.lock")
TICK = 30                                   # seconds between looks
HEAT_STRIKES = 2                            # looks in a row above the limit before warning
HEAT_COOLDOWN = 600                         # then stay quiet this long
PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
NAMES = {"fajr": ("Fajr", "الفجر"), "sunrise": ("Sunrise", "الشروق"), "dhuhr": ("Dhuhr", "الظهر"),
         "asr": ("Asr", "العصر"), "maghrib": ("Maghrib", "المغرب"), "isha": ("Isha", "العشاء")}


# ---------------------------------------------------------------- prayer times
# The standard sun formulas (the ones praytimes.org publishes). Jordan's Ministry
# of Awqaf: Fajr and Isha at 18 degrees below the horizon, Asr when a shadow is as
# long as the object (standard).

def _sin(d): return math.sin(math.radians(d))
def _cos(d): return math.cos(math.radians(d))
def _tan(d): return math.tan(math.radians(d))
def _asin(x): return math.degrees(math.asin(x))
def _acos(x): return math.degrees(math.acos(x))
def _atan2(y, x): return math.degrees(math.atan2(y, x))


def _julian(year, month, day):
    if month <= 2:
        year, month = year - 1, month + 12
    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def _sun(jd):
    """(declination in degrees, equation of time in hours)."""
    d = jd - 2451545.0
    g = (357.529 + 0.98560028 * d) % 360
    q = (280.459 + 0.98564736 * d) % 360
    lon = (q + 1.915 * _sin(g) + 0.020 * _sin(2 * g)) % 360
    e = 23.439 - 0.00000036 * d
    ra = (_atan2(_cos(e) * _sin(lon), _cos(lon)) / 15) % 24
    return _asin(_sin(e) * _sin(lon)), q / 15 - ra


def _hours(angle, lat, decl):
    """Hours from noon until the sun is `angle` degrees below the horizon (negative angle: above)."""
    x = (-_sin(angle) - _sin(decl) * _sin(lat)) / (_cos(decl) * _cos(lat))
    if abs(x) > 1:
        return None                          # the sun never gets there (far north in summer)
    return _acos(x) / 15


def prayer_times(day, lat, lon, tz_hours):
    """{name: datetime} for a date: fajr, sunrise, dhuhr, asr, maghrib, isha (naive local times)."""
    jd = _julian(day.year, day.month, day.day) - lon / 360
    decl, eqt = _sun(jd + 0.5)
    noon = 12 + tz_hours - lon / 15 - eqt
    asr_angle = -math.degrees(math.atan(1 / (1 + _tan(abs(lat - decl)))))
    spans = {"fajr": -(_hours(18, lat, decl) or 0), "sunrise": -(_hours(0.833, lat, decl) or 0),
             "dhuhr": 0.0 + 2 / 60,                                  # a couple of minutes past noon
             "asr": _hours(asr_angle, lat, decl) or 0,
             "maghrib": (_hours(0.833, lat, decl) or 0) + 1 / 60,
             "isha": _hours(18, lat, decl) or 0}
    base = datetime.datetime(day.year, day.month, day.day)
    return {name: base + datetime.timedelta(hours=noon + span) for name, span in spans.items()}


def next_prayer(now, lat, lon, tz_hours):
    """(name, datetime) of the next of the five prayers (tomorrow's fajr after isha)."""
    for offset in (0, 1):
        day = now.date() + datetime.timedelta(days=offset)
        times = prayer_times(day, lat, lon, tz_hours)
        for name in PRAYERS:
            if times[name] > now:
                return name, times[name]
    return None


def tz_hours(now=None):
    t = time.localtime(now if now is not None else time.time())
    return (t.tm_gmtoff or 0) / 3600


def prayer_line(now, settings):
    c = settings["care"]
    found = next_prayer(now, c["prayer_lat"], c["prayer_lon"], tz_hours(now.timestamp()))
    if not found:
        return ""
    name, at = found
    left = int((at - now).total_seconds() // 60)
    en, ar = NAMES[name]
    return f"{en} {ar}  {at.strftime('%H:%M')}  ·  in {left // 60}h {left % 60:02d}m" if left >= 60 \
        else f"{en} {ar}  {at.strftime('%H:%M')}  ·  in {left} min"


# ---------------------------------------------------------------- heat

def cpu_temp(root="/sys/class/hwmon"):
    """The CPU package temperature in C (None if the laptop doesn't say)."""
    best = None
    for hw in sorted(glob.glob(os.path.join(root, "hwmon*"))):
        if _read(os.path.join(hw, "name")) in ("coretemp", "k10temp", "zenpower"):
            for f in sorted(glob.glob(os.path.join(hw, "temp*_input"))):
                raw = _read(f)
                if raw.isdigit():
                    value = int(raw) / 1000
                    best = value if best is None else max(best, value)
    return best


def nvidia_awake(root="/sys/bus/pci/devices"):
    """True only if the NVIDIA chip is already awake: asking a sleeping one would wake it."""
    for dev in glob.glob(os.path.join(root, "*")):
        if _read(os.path.join(dev, "vendor")) == "0x10de" and _read(os.path.join(dev, "class")).startswith("0x03"):
            return _read(os.path.join(dev, "power", "runtime_status")) == "active"
    return False


def gpu_temp():
    if not nvidia_awake():
        return None
    out = _run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
    return float(out.splitlines()[0]) if out and out.splitlines()[0].strip().isdigit() else None


class Heat:
    """Warns once when a chip stays above its limit for a minute, then waits ten minutes."""

    def __init__(self):
        self.strikes = {}
        self.quiet_until = 0.0

    def look(self, now, temps, limits):
        """temps/limits: {'CPU': 91.0, ...}. Returns the text to warn with, or None."""
        hot = [(k, v) for k, v in temps.items() if v is not None and v >= limits.get(k, 999)]
        for k in list(self.strikes):
            if k not in dict(hot):
                self.strikes[k] = 0
        for k, _v in hot:
            self.strikes[k] = self.strikes.get(k, 0) + 1
        if now < self.quiet_until or not any(self.strikes.get(k, 0) >= HEAT_STRIKES for k, _ in hot):
            return None
        self.quiet_until = now + HEAT_COOLDOWN
        return " and ".join(f"{k} is at {v:.0f}°C" for k, v in hot)


# ---------------------------------------------------------------- water

class Water:
    """Counts the minutes you're really at the laptop (not locked, gaming or focusing)."""

    def __init__(self):
        self.seconds = 0

    def look(self, active, minutes, step=TICK):
        if not active:
            return False
        self.seconds += step
        if self.seconds >= minutes * 60:
            self.seconds = 0
            return True
        return False


# ---------------------------------------------------------------- doing it

_island, _notify, _bin = sh.island, sh.notify, sh.bin_path
_read, _run = sh.read_text, sh.out


def _heat_alert(text):
    """A warning with a one-tap switch to Quiet mode (waits for the tap in the background)."""
    def ask():
        try:
            out = subprocess.run(["notify-send", "-a", "Lennox", "-i", "dialog-warning", "-u", "critical", "-t", "20000",
                                  "-A", "quiet=Switch to Quiet mode", "--wait", "It's getting hot", text],
                                 capture_output=True, text=True, timeout=40, check=False).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return
        if out == "quiet":
            subprocess.run([_bin("lennox-perf"), "quiet"], capture_output=True, check=False)
    threading.Thread(target=ask, daemon=True).start()
    _island("temperature-symbolic", "Getting hot: " + text, "6")


def busy():
    """Gaming or focusing: no reminders then."""
    if _run([_bin("lennox-mode"), "game", "status"]) == "on":
        return True
    try:
        with open(os.path.join(S.STATE_DIR, "focus.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("active"))
    except (OSError, ValueError, AttributeError):
        return False


def locked():
    return subprocess.run(["pidof", "hyprlock"], capture_output=True, check=False).returncode == 0


def step(state, settings, now_dt):
    """One look. `state` holds Heat, Water and the prayer reminders already sent."""
    c = settings["care"]
    away = locked()
    gaming = busy()
    if c["water"] and state["water"].look(not away and not gaming, c["water_minutes"]):
        _notify("Time for some water", "You've been at it for a while. A few sips and a stretch?", "weather-showers-symbolic")
        _island("weather-showers-symbolic", "Drink some water", "5")
    if c["heat"]:
        temps = {"CPU": cpu_temp()}
        if gaming:
            temps["GPU"] = gpu_temp()
        text = state["heat"].look(now_dt.timestamp(), temps, {"CPU": c["heat_cpu"], "GPU": c["heat_gpu"]})
        if text:
            _heat_alert(text)
    if c["prayer"] and not away:
        for day in (now_dt.date(), now_dt.date() + datetime.timedelta(days=1)):
            times = prayer_times(day, c["prayer_lat"], c["prayer_lon"], tz_hours(now_dt.timestamp()))
            for name in PRAYERS:
                en, ar = NAMES[name]
                for lead, text in ((c["prayer_remind"], f"{en} {ar} in {c['prayer_remind']} minutes"), (0, f"{en} {ar}: it's time")):
                    if lead == 0 and not c["prayer_at_time"]:
                        continue
                    due = times[name] - datetime.timedelta(minutes=lead)
                    key = (str(day), name, lead)
                    if key not in state["sent"] and 0 <= (now_dt - due).total_seconds() < 120:
                        state["sent"].add(key)
                        _notify(f"{en}  {ar}", text, "weather-clear-night-symbolic")
                        _island("weather-clear-night-symbolic", text, "6")
    if len(state["sent"]) > 200:
        state["sent"].clear()


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")  # noqa: SIM115  held for the life of the process
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    state = {"water": Water(), "heat": Heat(), "sent": set()}
    while True:
        try:
            settings = S.load()
            c = settings["care"]
            if c["water"] or c["heat"] or c["prayer"]:
                step(state, settings, datetime.datetime.now())
        except Exception:  # noqa: BLE001  a flaky tool must never stop the watcher
            pass
        time.sleep(TICK)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "prayer"
    if mode == "watch":
        return watch()
    settings = S.load()
    if mode == "prayer":
        c = settings["care"]
        now = datetime.datetime.now()
        times = prayer_times(now.date(), c["prayer_lat"], c["prayer_lon"], tz_hours())
        if "--json" in argv:
            print(json.dumps({k: v.strftime("%H:%M") for k, v in times.items()} | {"next": prayer_line(now, settings)},
                             ensure_ascii=False))
        else:
            for name, at in times.items():
                print(f"{NAMES[name][0]:8} {NAMES[name][1]:8} {at.strftime('%H:%M')}")
            print("Next:", prayer_line(now, settings))
    elif mode == "heat":
        print(json.dumps({"cpu": cpu_temp(), "gpu": gpu_temp()}))
    else:
        print("usage: lennox-care watch | prayer [--json] | heat", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
