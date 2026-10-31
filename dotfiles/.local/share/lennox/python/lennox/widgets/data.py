"""Data for the widgets: system stats, battery, weather, greeting, notes.

Plain Python (no GTK) so every piece can be tested on its own. Anything
that can fail (missing sensors, no internet) returns None or raises
WeatherError instead of crashing the widgets.
"""

import datetime
import glob
import hashlib
import json
import os
import pwd
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

from .. import settings as S

WEATHER_CACHE = os.path.join(S.CACHE_DIR, "weather.json")
ART_CACHE = os.path.join(S.CACHE_DIR, "art")
NOTES_FILE = os.path.join(S.CONFIG_DIR, "notes.txt")
WEATHER_MAX_AGE = 30 * 60
USER_AGENT = "Lennox-widgets/1.0 (Hyprland desktop)"


# ---------------------------------------------------------------- you

def display_name(configured=""):
    """The name for the greeting: the setting, else your account's full name."""
    if configured.strip():
        return configured.strip()
    try:
        entry = pwd.getpwuid(os.getuid())
    except KeyError:
        return ""
    full = entry.pw_gecos.split(",")[0].strip()
    if full:
        return full.split()[0]
    return entry.pw_name.capitalize()


def greeting(hour):
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Late night"


def avatar_path():
    """Your picture: ~/.face, or the one AccountsService (SDDM) knows."""
    candidates = [
        os.path.expanduser("~/.face"),
        os.path.expanduser("~/.face.icon"),
        f"/var/lib/AccountsService/icons/{pwd.getpwuid(os.getuid()).pw_name}",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.R_OK):
            return path
    return None


def uptime(path="/proc/uptime"):
    try:
        with open(path) as f:
            seconds = int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return ""
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"up {days} d {hours} h"
    if hours:
        return f"up {hours} h {minutes} min"
    return f"up {minutes} min"


def format_time(now, h24, seconds=False):
    if h24:
        return now.strftime("%H:%M:%S" if seconds else "%H:%M")
    text = now.strftime("%I:%M:%S" if seconds else "%I:%M").lstrip("0")
    return text


def format_date(now):
    return now.strftime("%A, %-d %B")


# ---------------------------------------------------------------- system

class CpuMeter:
    """CPU usage in percent between two calls."""

    def __init__(self, path="/proc/stat"):
        self.path = path
        self._last = None

    def _sample(self):
        with open(self.path) as f:
            fields = [int(x) for x in f.readline().split()[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
        return sum(fields), idle

    def percent(self):
        try:
            total, idle = self._sample()
        except (OSError, ValueError, IndexError):
            return None
        last, self._last = self._last, (total, idle)
        if last is None or total <= last[0]:
            return 0.0
        busy = (total - last[0]) - (idle - last[1])
        return max(0.0, min(100.0, 100.0 * busy / (total - last[0])))


def memory(path="/proc/meminfo"):
    """(percent used, used GiB, total GiB) or None."""
    info = {}
    try:
        with open(path) as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])
    except (OSError, ValueError, IndexError):
        return None
    total = info.get("MemTotal")
    available = info.get("MemAvailable")
    if not total or available is None:
        return None
    used = total - available
    return 100.0 * used / total, used / 1048576, total / 1048576


def disk(path="/"):
    """(percent used, free GiB) or None."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    if not usage.total:
        return None
    return 100.0 * usage.used / usage.total, usage.free / 1073741824


def battery(root="/sys/class/power_supply"):
    """(percent, status) for the first battery, or None on a desktop."""
    for bat in sorted(glob.glob(os.path.join(root, "BAT*"))):
        try:
            with open(os.path.join(bat, "capacity")) as f:
                percent = int(f.read().strip())
        except (OSError, ValueError):
            continue
        try:
            with open(os.path.join(bat, "status")) as f:
                status = f.read().strip()
        except OSError:
            status = "Unknown"
        return max(0, min(100, percent)), status
    return None


def temperature(hwmon="/sys/class/hwmon", thermal="/sys/class/thermal"):
    """CPU temperature in °C, or None."""
    preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz")
    found = {}
    for mon in glob.glob(os.path.join(hwmon, "hwmon*")):
        try:
            with open(os.path.join(mon, "name")) as f:
                name = f.read().strip()
            with open(os.path.join(mon, "temp1_input")) as f:
                found.setdefault(name, int(f.read().strip()) / 1000)
        except (OSError, ValueError):
            continue
    for name in preferred:
        if name in found:
            return found[name]
    for zone in sorted(glob.glob(os.path.join(thermal, "thermal_zone*"))):
        try:
            with open(os.path.join(zone, "temp")) as f:
                value = int(f.read().strip()) / 1000
        except (OSError, ValueError):
            continue
        if 0 < value < 150:
            return value
    return None


# ---------------------------------------------------------------- weather

class WeatherError(Exception):
    pass


# WMO weather codes (Open-Meteo): description, day icon, night icon
WMO = {
    0: ("Clear", "weather-clear-symbolic", "weather-clear-night-symbolic"),
    1: ("Mostly clear", "weather-few-clouds-symbolic", "weather-few-clouds-night-symbolic"),
    2: ("Partly cloudy", "weather-few-clouds-symbolic", "weather-few-clouds-night-symbolic"),
    3: ("Cloudy", "weather-overcast-symbolic", "weather-overcast-symbolic"),
    45: ("Fog", "weather-fog-symbolic", "weather-fog-symbolic"),
    48: ("Freezing fog", "weather-fog-symbolic", "weather-fog-symbolic"),
    51: ("Light drizzle", "weather-showers-scattered-symbolic", "weather-showers-scattered-symbolic"),
    53: ("Drizzle", "weather-showers-scattered-symbolic", "weather-showers-scattered-symbolic"),
    55: ("Heavy drizzle", "weather-showers-symbolic", "weather-showers-symbolic"),
    56: ("Freezing drizzle", "weather-showers-scattered-symbolic", "weather-showers-scattered-symbolic"),
    57: ("Freezing drizzle", "weather-showers-symbolic", "weather-showers-symbolic"),
    61: ("Light rain", "weather-showers-scattered-symbolic", "weather-showers-scattered-symbolic"),
    63: ("Rain", "weather-showers-symbolic", "weather-showers-symbolic"),
    65: ("Heavy rain", "weather-showers-symbolic", "weather-showers-symbolic"),
    66: ("Freezing rain", "weather-showers-symbolic", "weather-showers-symbolic"),
    67: ("Freezing rain", "weather-showers-symbolic", "weather-showers-symbolic"),
    71: ("Light snow", "weather-snow-symbolic", "weather-snow-symbolic"),
    73: ("Snow", "weather-snow-symbolic", "weather-snow-symbolic"),
    75: ("Heavy snow", "weather-snow-symbolic", "weather-snow-symbolic"),
    77: ("Snow grains", "weather-snow-symbolic", "weather-snow-symbolic"),
    80: ("Showers", "weather-showers-scattered-symbolic", "weather-showers-scattered-symbolic"),
    81: ("Showers", "weather-showers-symbolic", "weather-showers-symbolic"),
    82: ("Heavy showers", "weather-showers-symbolic", "weather-showers-symbolic"),
    85: ("Snow showers", "weather-snow-symbolic", "weather-snow-symbolic"),
    86: ("Snow showers", "weather-snow-symbolic", "weather-snow-symbolic"),
    95: ("Thunderstorm", "weather-storm-symbolic", "weather-storm-symbolic"),
    96: ("Thunderstorm", "weather-storm-symbolic", "weather-storm-symbolic"),
    99: ("Thunderstorm", "weather-storm-symbolic", "weather-storm-symbolic"),
}


def describe(code, is_day=True):
    """(description, icon name) for a WMO weather code."""
    text, day, night = WMO.get(code, ("", "weather-severe-alert-symbolic", "weather-severe-alert-symbolic"))
    return text, (day if is_day else night)


def _get_json(url, opener=None):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            reason = json.loads(e.read().decode("utf-8")).get("reason")
        except (ValueError, OSError, AttributeError):
            reason = None
        raise WeatherError(reason or f"Weather service error ({e.code})") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise WeatherError("No internet connection") from None
    except ValueError:
        raise WeatherError("The weather service sent something unexpected") from None
    if not isinstance(data, dict):
        raise WeatherError("The weather service sent something unexpected")
    if data.get("error"):
        raise WeatherError(str(data.get("reason") or "Weather service error"))
    return data


def geocode(city, opener=None):
    """(place name, latitude, longitude) for a city name."""
    query = urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    data = _get_json("https://geocoding-api.open-meteo.com/v1/search?" + query, opener)
    results = data.get("results") or []
    if not results:
        raise WeatherError(f"Can't find \"{city}\". Try a bigger city nearby.")
    r = results[0]
    place = r.get("name", city)
    if r.get("country_code"):
        place += f", {r['country_code']}"
    return place, float(r["latitude"]), float(r["longitude"])


def parse_forecast(data, place, unit):
    """Turn an Open-Meteo forecast answer into what the cards show."""
    try:
        current = data["current"]
        daily = data["daily"]
        is_day = bool(current.get("is_day", 1))
        text, icon = describe(int(current["weather_code"]), is_day)
        days = []
        for i, day in enumerate(daily["time"][:3]):
            name = "Today" if i == 0 else datetime.date.fromisoformat(day).strftime("%a")
            dtext, dicon = describe(int(daily["weather_code"][i]))
            days.append({
                "name": name, "icon": dicon, "text": dtext,
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
            })
        return {
            "place": place,
            "unit": "°F" if unit == "fahrenheit" else "°C",
            "temp": round(current["temperature_2m"]),
            "feels": round(current.get("apparent_temperature", current["temperature_2m"])),
            "text": text,
            "icon": icon,
            "days": days,
        }
    except (KeyError, TypeError, ValueError, IndexError):
        raise WeatherError("The weather service sent something unexpected") from None


def _read_cache():
    try:
        with open(WEATHER_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(cache):
    try:
        os.makedirs(os.path.dirname(WEATHER_CACHE), exist_ok=True)
        tmp = WEATHER_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, WEATHER_CACHE)
    except OSError:
        pass


def weather(city, unit, force=False, opener=None, now=None):
    """The weather for `city`, at most 30 minutes old. Raises WeatherError.

    Runs in a background thread: it may wait for the network.
    """
    city = city.strip()
    if not city:
        raise WeatherError("Set your city in Lennox Settings > Widgets")
    now = time.time() if now is None else now
    cache = _read_cache()
    key = f"{city.lower()}|{unit}"
    entry = cache.get("forecast", {})
    if not force and entry.get("key") == key and now - entry.get("time", 0) < WEATHER_MAX_AGE:
        return entry["data"]

    places = cache.setdefault("places", {})
    try:
        if city.lower() in places:
            place, lat, lon = places[city.lower()]
        else:
            place, lat, lon = geocode(city, opener)
            places[city.lower()] = [place, lat, lon]
        query = urllib.parse.urlencode({
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
            "current": "temperature_2m,apparent_temperature,weather_code,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto", "forecast_days": 3,
            "temperature_unit": "fahrenheit" if unit == "fahrenheit" else "celsius",
        })
        result = parse_forecast(_get_json("https://api.open-meteo.com/v1/forecast?" + query, opener), place, unit)
    except WeatherError:
        # Offline or rate limited: an older forecast for the same place beats nothing
        if entry.get("key") == key and now - entry.get("time", 0) < 6 * 3600:
            return dict(entry["data"], stale=True)
        raise
    cache["forecast"] = {"key": key, "time": now, "data": result}
    _write_cache(cache)
    return result


# ---------------------------------------------------------------- media art

def art_file(url, opener=None):
    """A local file for an MPRIS art URL (downloads https art once)."""
    if not url:
        return None
    if url.startswith("file://"):
        path = urllib.parse.unquote(url[len("file://"):])
        return path if os.path.isfile(path) else None
    if not url.startswith(("https://", "http://")):
        return None
    name = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = os.path.join(ART_CACHE, name)
    if os.path.isfile(path):
        return path
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=10) as response:
            body = response.read(4 * 1024 * 1024 + 1)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None
    if not body or len(body) > 4 * 1024 * 1024:
        return None
    try:
        os.makedirs(ART_CACHE, exist_ok=True)
        # Keep the cache small: drop the oldest beyond 60 covers
        covers = sorted(glob.glob(os.path.join(ART_CACHE, "*")), key=os.path.getmtime)
        for old in covers[:-60]:
            os.unlink(old)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, path)
    except OSError:
        return None
    return path


# ---------------------------------------------------------------- notes

def load_notes():
    try:
        with open(NOTES_FILE, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def save_notes(text):
    try:
        os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
        tmp = NOTES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, NOTES_FILE)
        return True
    except OSError:
        return False
