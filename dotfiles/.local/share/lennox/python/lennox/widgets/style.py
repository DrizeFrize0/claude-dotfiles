"""CSS for the widgets, colored from the wallpaper (colors.json)."""

import json
import os

from .. import settings as S

COLORS_FILE = os.path.join(S.CONFIG_DIR, "colors.json")
CUSTOM_CSS = os.path.join(S.CONFIG_DIR, "widgets.css")

# ML4W's default teal, used until the first wallpaper is themed
FALLBACK = {
    "primary": "#81d5cd", "on_primary": "#003734", "primary_container": "#00504b",
    "on_primary_container": "#9df2e9", "secondary": "#b0ccc8", "secondary_container": "#324b49",
    "on_secondary_container": "#cce8e4", "tertiary": "#afc9e7", "surface": "#0e1514",
    "surface_container": "#1a2120", "surface_container_high": "#252b2a",
    "surface_container_highest": "#2f3635", "on_surface": "#dde4e2",
    "on_surface_variant": "#bec9c6", "outline": "#899391", "outline_variant": "#3f4947",
    "error": "#ffb4ab",
}


def load_colors(path=COLORS_FILE):
    colors = dict(FALLBACK)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return colors
    if isinstance(data, dict):
        for name, value in data.items():
            if isinstance(value, str) and value.startswith("#") and len(value) in (7, 9):
                colors[name] = value
    return colors


BASE = """
/* ---------------------------------------------- shared */
.lennox-widgets, .lennox-dashboard {
    font-family: "Inter", "Fira Sans", sans-serif;
    color: @on_surface;
}
window.lennox-widgets, window.lennox-dashboard-window { background: transparent; }

.card {
    background-color: alpha(@surface_container, 0.72);
    border: 1px solid alpha(@outline_variant, 0.6);
    border-radius: 20px;
    padding: 16px 18px;
}
.card-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
    color: @primary;
}
.dim { color: @on_surface_variant; }
.small { font-size: 12px; }

/* ---------------------------------------------- clock */
.clock-time {
    font-size: 84px;
    font-weight: 300;
    letter-spacing: -2px;
    color: @on_surface;
}
.clock-ampm { font-size: 22px; font-weight: 600; color: @primary; margin-bottom: 18px; }
.clock-date { font-size: 20px; font-weight: 500; color: @primary; }
.clock-greeting { font-size: 16px; color: @on_surface_variant; }
.lennox-widgets .clock-time, .lennox-widgets .clock-date,
.lennox-widgets .clock-greeting, .lennox-widgets .clock-ampm {
    text-shadow: 0 2px 10px alpha(black, 0.55);
}
.lennox-dashboard .clock-time { font-size: 56px; }

/* ---------------------------------------------- weather */
.weather-icon { color: @primary; }
.weather-temp { font-size: 34px; font-weight: 300; }
.weather-day { padding: 6px 4px; border-radius: 12px; background-color: alpha(@surface_container_highest, 0.5); }

/* ---------------------------------------------- media */
.media-art {
    border-radius: 14px;
    background-color: @primary_container;
    color: @on_primary_container;
}
.media-title { font-size: 15px; font-weight: 600; }
.media-button {
    min-width: 34px; min-height: 34px;
    border-radius: 999px;
    padding: 0;
    background: alpha(@surface_container_highest, 0.6);
    color: @on_surface;
    border: none;
    box-shadow: none;
}
.media-button:hover { background: alpha(@primary, 0.25); }
.media-button.play { background: @primary; color: @on_primary; }
.media-button.play:hover { background: mix(@primary, white, 0.15); }

/* ---------------------------------------------- system */
levelbar trough { min-height: 6px; border-radius: 99px; background-color: alpha(@outline_variant, 0.7); border: none; }
levelbar block { border-radius: 99px; border: none; min-height: 6px; }
levelbar block.filled { background-color: @primary; }
levelbar block.empty { background-color: transparent; }
levelbar.warning block.filled { background-color: @tertiary; }
levelbar.critical block.filled { background-color: @error; }

/* ---------------------------------------------- dashboard */
.lennox-dashboard {
    background-color: alpha(@surface, 0.88);
    border: 1px solid alpha(@outline_variant, 0.8);
    border-radius: 24px;
}
.lennox-dashboard .card { background-color: alpha(@surface_container_high, 0.75); }
.avatar {
    border-radius: 999px;
    background-color: @primary;
    color: @on_primary;
    font-size: 22px;
    font-weight: 700;
}
.profile-name { font-size: 18px; font-weight: 700; }
.icon-button {
    min-width: 38px; min-height: 38px;
    border-radius: 999px;
    padding: 0;
    background: alpha(@surface_container_highest, 0.7);
    color: @on_surface;
    border: none;
    box-shadow: none;
}
.icon-button:hover { background: alpha(@primary, 0.25); }
.icon-button.danger:hover { background: alpha(@error, 0.3); }
.action {
    border-radius: 16px;
    padding: 10px 4px;
    background: alpha(@surface_container_highest, 0.6);
    color: @on_surface;
    border: none;
    box-shadow: none;
}
.action:hover { background: alpha(@primary, 0.22); }
.action image { color: @primary; }
.action label { font-size: 11px; }
scale trough { min-height: 8px; border-radius: 99px; border: none; background-color: alpha(@outline_variant, 0.8); }
scale highlight { border-radius: 99px; background-color: @primary; }
scale slider { min-width: 16px; min-height: 16px; margin: -5px; border-radius: 99px; background-color: @on_primary_container; box-shadow: none; border: none; }
calendar {
    background: transparent;
    border: none;
    color: @on_surface;
}
calendar > header { border: none; background: transparent; }
calendar > header > button { background: transparent; border: none; box-shadow: none; color: @on_surface; }
calendar > grid > label.day-name { color: @on_surface_variant; font-weight: 600; }
calendar > grid > label.day-number { border-radius: 99px; padding: 4px; }
calendar > grid > label.day-number.other-month { color: alpha(@on_surface, 0.3); }
calendar > grid > label.today { background-color: @primary; color: @on_primary; font-weight: 700; }
calendar > grid > label:selected { background-color: alpha(@primary, 0.3); color: @on_surface; }
.notes, .notes text {
    background-color: transparent;
    color: @on_surface;
    font-size: 14px;
}
.notes-frame { border-radius: 14px; background-color: alpha(@surface_container_highest, 0.5); padding: 8px; }
.lennox-dashboard scrolledwindow, .lennox-dashboard viewport { background: transparent; }
"""


def css(colors=None):
    colors = colors or load_colors()
    defines = "".join(f"@define-color {name} {value};\n" for name, value in sorted(colors.items())
                      if name.replace("_", "").isalnum())
    custom = ""
    try:
        with open(CUSTOM_CSS, encoding="utf-8") as f:
            custom = "\n/* ~/.config/lennox/widgets.css */\n" + f.read()
    except OSError:
        pass
    return defines + BASE + custom
