#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
R="$(cd "$SP/.." && pwd)"
H=$SP/whome; rm -rf $H $SP/wshots; mkdir -p $H/.config $H/.cache/lennox $H/run
rsync -a $R/dotfiles/.config/lennox $H/.config/
rsync -a $R/dotfiles/.local $H/
/usr/bin/python3.12 - "$H" <<'PY'
import json, sys, time
h = sys.argv[1]
p = f"{h}/.config/lennox/settings.json"
d = json.load(open(p))
d.setdefault("widgets", {}).update({"show_system": True, "weather_city": "Toronto", "position": "top-left", "name": "Lennox", "island": False})
json.dump(d, open(p, "w"), indent=2)
data = {"place": "Toronto, CA", "unit": "°C", "temp": 8, "feels": 4, "text": "Partly cloudy",
        "icon": "weather-few-clouds-night-symbolic",
        "days": [{"name": "Today", "icon": "weather-few-clouds-symbolic", "text": "Partly cloudy", "high": 11, "low": 3},
                 {"name": "Thu", "icon": "weather-showers-scattered-symbolic", "text": "Light rain", "high": 9, "low": 4},
                 {"name": "Fri", "icon": "weather-clear-symbolic", "text": "Clear", "high": 13, "low": 2}]}
json.dump({"forecast": {"key": "toronto|celsius", "time": time.time(), "data": data}}, open(f"{h}/.cache/lennox/weather.json", "w"))
PY
HOME=$H XDG_RUNTIME_DIR=$H/run timeout -k 5 120 xvfb-run -a -s "-screen 0 1280x900x24" dbus-run-session bash $SP/widgets_gui_test.sh
