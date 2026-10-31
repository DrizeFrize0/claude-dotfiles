"""Unit tests for lennox.widgets.data (no GTK)."""
import io
import json
import os
import sys
import tempfile
import urllib.error

HOME = tempfile.mkdtemp()
os.environ["HOME"] = HOME
os.environ["XDG_CONFIG_HOME"] = os.path.join(HOME, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(HOME, ".cache")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/dotfiles/.local/share/lennox/python")
from lennox.widgets import data as D  # noqa: E402

fails = 0


def check(cond, what):
    global fails
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        fails += 1


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


T = tempfile.mkdtemp()

# greeting / time
check(D.greeting(9) == "Good morning" and D.greeting(13) == "Good afternoon" and D.greeting(19) == "Good evening"
      and D.greeting(2) == "Late night" and D.greeting(23) == "Late night", "greetings by hour")
import datetime  # noqa: E402
t = datetime.datetime(2026, 10, 28, 21, 5)
check(D.format_time(t, True) == "21:05" and D.format_time(t, False) == "9:05", "24h / 12h clock")
check(D.format_date(t) == "Wednesday, 28 October", "date text: " + D.format_date(t))
check(D.display_name("  Lennox ") == "Lennox", "configured name wins")
check(isinstance(D.display_name(""), str) and D.display_name("") != "", "account name fallback: " + D.display_name(""))

# uptime
write(f"{T}/uptime", "200000.5 1000.0\n"); check(D.uptime(f"{T}/uptime") == "up 2 d 7 h", "uptime days")
write(f"{T}/uptime", "4000 1\n"); check(D.uptime(f"{T}/uptime") == "up 1 h 6 min", "uptime hours")
write(f"{T}/uptime", "garbage"); check(D.uptime(f"{T}/uptime") == "", "uptime garbage")
check(D.uptime(f"{T}/nope") == "", "uptime missing file")

# cpu
write(f"{T}/stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
m = D.CpuMeter(f"{T}/stat"); check(m.percent() == 0.0, "cpu first sample = 0")
write(f"{T}/stat", "cpu  150 0 150 900 0 0 0 0 0 0\n"); check(abs(m.percent() - 50.0) < 0.01, "cpu 50%")
check(D.CpuMeter(f"{T}/missing").percent() is None, "cpu missing file")

# memory / disk
write(f"{T}/meminfo", "MemTotal:       16000000 kB\nMemFree: 1 kB\nMemAvailable:    4000000 kB\n")
pct, used, total = D.memory(f"{T}/meminfo"); check(abs(pct - 75) < 0.01 and total > 15, "memory 75%")
write(f"{T}/meminfo", "MemTotal: 0 kB\n"); check(D.memory(f"{T}/meminfo") is None, "memory broken")
check(D.disk("/") is not None and D.disk("/nope/x") is None, "disk usage")

# battery
ps = f"{T}/ps"
check(D.battery(ps) is None, "no battery = desktop")
write(f"{ps}/AC/online", "1"); write(f"{ps}/BAT0/capacity", "57\n"); write(f"{ps}/BAT0/status", "Charging\n")
check(D.battery(ps) == (57, "Charging"), "battery read")
write(f"{ps}/BAT0/capacity", "x"); write(f"{ps}/BAT1/capacity", "120"); write(f"{ps}/BAT1/status", "Full")
check(D.battery(ps) == (100, "Full"), "broken BAT0 skipped, clamped")

# temperature
hw = f"{T}/hwmon"; th = f"{T}/thermal"
write(f"{hw}/hwmon0/name", "nvme\n"); write(f"{hw}/hwmon0/temp1_input", "41000\n")
write(f"{hw}/hwmon1/name", "coretemp\n"); write(f"{hw}/hwmon1/temp1_input", "63500\n")
check(D.temperature(hw, th) == 63.5, "coretemp preferred")
write(f"{T}/hw2/hwmon0/name", "nvme"); write(f"{T}/hw2/hwmon0/temp1_input", "x")
write(f"{th}/thermal_zone0/temp", "48000")
check(D.temperature(f"{T}/hw2", th) == 48.0, "thermal zone fallback")
check(D.temperature(f"{T}/none", f"{T}/none") is None, "no sensors")

# weather
for code in D.WMO:
    text, icon = D.describe(code, False)
    check(text and icon.endswith("-symbolic"), f"wmo {code}") if code in (0, 3, 95) else None
check(D.describe(1234)[1] == "weather-severe-alert-symbolic", "unknown code icon")

GEO = {"results": [{"name": "Toronto", "latitude": 43.70643, "longitude": -79.39864, "country_code": "CA"}]}
FORECAST = {
    "current": {"time": "2026-10-28T21:00", "temperature_2m": 7.6, "apparent_temperature": 4.2,
                "weather_code": 2, "is_day": 0},
    "daily": {"time": ["2026-10-28", "2026-10-29", "2026-10-30"], "weather_code": [2, 61, 0],
              "temperature_2m_max": [11.2, 9.0, 12.5], "temperature_2m_min": [3.1, 4.4, 2.0]},
}
calls = []


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_with(responses):
    def opener(request, timeout=None):
        url = request.full_url
        calls.append(url)
        for key, value in responses.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return Resp(json.dumps(value).encode())
        raise AssertionError("unexpected url " + url)
    return opener


good = opener_with({"geocoding-api": GEO, "api.open-meteo.com/v1/forecast": FORECAST})
w = D.weather("Toronto", "celsius", opener=good, now=1000)
check(w["temp"] == 8 and w["place"] == "Toronto, CA" and w["unit"] == "°C" and len(w["days"]) == 3, "weather parsed")
check(w["icon"] == "weather-few-clouds-night-symbolic" and w["days"][1]["text"] == "Light rain"
      and w["days"][1]["name"] == "Thu" and w["days"][0]["name"] == "Today", "weather icons/days")
check("temperature_unit=celsius" in calls[-1] and "latitude=43.7064" in calls[-1], "forecast url")
n = len(calls)
w2 = D.weather("toronto", "celsius", opener=good, now=1000 + 600)
check(len(calls) == n and w2 == w, "cache hit within 30 min (case-insensitive)")
D.weather("Toronto", "fahrenheit", opener=good, now=1700)
check(len(calls) == n + 1 and "temperature_unit=fahrenheit" in calls[-1], "unit change refetches, geocode cached")

limited = opener_with({"api.open-meteo.com/v1/forecast": {"error": True, "reason": "Daily API request limit exceeded."}})
stale = D.weather("Toronto", "fahrenheit", opener=limited, now=1700 + 3600)
check(stale.get("stale") is True, "rate limited -> stale cached forecast")
try:
    D.weather("Toronto", "fahrenheit", opener=limited, now=1700 + 7 * 3600)
    check(False, "too-old cache should raise")
except D.WeatherError as e:
    check("limit" in str(e), "rate limit message shown: " + str(e))

offline = opener_with({"geocoding-api": urllib.error.URLError("no route")})
try:
    D.weather("Paris", "celsius", opener=offline, now=5000)
    check(False, "offline should raise")
except D.WeatherError as e:
    check(str(e) == "No internet connection", "offline message")
nowhere = opener_with({"geocoding-api": {"generationtime_ms": 0.2}})
try:
    D.weather("Xyzzyville", "celsius", opener=nowhere, now=5000)
    check(False)
except D.WeatherError as e:
    check("Can't find" in str(e), "unknown city message")
try:
    D.weather("  ", "celsius", opener=good)
    check(False)
except D.WeatherError as e:
    check("Set your city" in str(e), "no city message")
broken = opener_with({"geocoding-api": GEO, "api.open-meteo.com/v1/forecast": {"current": {}}})
try:
    D.weather("Berlin", "celsius", opener=broken, now=9000)
    check(False)
except D.WeatherError as e:
    check("unexpected" in str(e), "malformed forecast handled")
write(D.WEATHER_CACHE, "{not json")
check(D.weather("Toronto", "celsius", opener=good, now=99999)["temp"] == 8, "corrupt cache ignored")

# art
img = f"{T}/cover.png"; open(img, "wb").write(b"\x89PNG fake")
check(D.art_file("file://" + img.replace(" ", "%20")) == img, "file:// art")
check(D.art_file("file:///nope.png") is None and D.art_file("") is None and D.art_file("data:x") is None, "bad art urls")


def art_opener(request, timeout=None):
    return Resp(b"JPEGDATA")


p = D.art_file("https://i.scdn.co/image/abc", opener=art_opener)
check(p and open(p, "rb").read() == b"JPEGDATA", "https art downloaded")
check(D.art_file("https://i.scdn.co/image/abc", opener=lambda *a, **k: 1 / 0) == p, "https art cached")
check(D.art_file("https://x/huge", opener=lambda r, timeout=None: Resp(b"x" * (4 * 1024 * 1024 + 5))) is None, "huge art refused")
check(D.art_file("https://x/fail", opener=lambda r, timeout=None: (_ for _ in ()).throw(urllib.error.URLError("x"))) is None, "art offline")

# notes
check(D.load_notes() == "", "no notes yet")
check(D.save_notes("buy protein\nfix server ✓") and D.load_notes() == "buy protein\nfix server ✓", "notes round trip")

print("\nFAILURES:", fails)
sys.exit(1 if fails else 0)
