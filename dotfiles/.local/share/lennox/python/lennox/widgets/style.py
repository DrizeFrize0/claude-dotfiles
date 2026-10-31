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

/* Dynamic island: black like the iPhone's, whatever the wallpaper */
window.lennox-island-window { background: transparent; }
.lennox-island {
    background-color: #000000;
    color: #ffffff;
    border-radius: 22px;
    /* No drop shadow: the window is exactly the pill's size, so a shadow
       would be cut off into grey corners behind the round ends. The glow
       ring is drawn inside: a colored hairline and a soft inner glow */
    border: 1px solid alpha(white, 0.08);
    box-shadow: inset 0 1px alpha(white, 0.10);
    transition: border-radius 300ms cubic-bezier(0.2, 0.9, 0.3, 1.0), border-color 400ms ease, box-shadow 400ms ease;
}
.lennox-island.glow-accent { border-color: alpha(@primary, 0.55); box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 9px alpha(@primary, 0.30); }
.lennox-island.glow-amber { border-color: alpha(#ff9f0a, 0.60); box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 9px alpha(#ff9f0a, 0.30); }
.lennox-island.glow-green { border-color: alpha(#30d158, 0.60); box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 9px alpha(#30d158, 0.28); }
.lennox-island.glow-red { border-color: alpha(#ff453a, 0.65); box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 9px alpha(#ff453a, 0.32); }
.lennox-island.glow-blue { border-color: alpha(#0a84ff, 0.65); box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 9px alpha(#0a84ff, 0.32); }
/* Ringing: the amber ring pulses (only while ringing) */
@keyframes island-pulse {
    from { box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 4px alpha(#ff9f0a, 0.20); }
    to { box-shadow: inset 0 1px alpha(white, 0.10), inset 0 0 16px alpha(#ff9f0a, 0.55); }
}
.lennox-island.ringing { animation: island-pulse 900ms ease-in-out infinite alternate; }
.island-page { padding: 0 11px; min-width: 96px; }
.island-page.music, .island-page.timer, .island-page.event, .island-page.call,
.island-page.focus, .island-page.stopwatch { min-width: 180px; }
.island-page.expanded { padding: 0 12px 12px 12px; min-width: 280px; }
.lennox-island.expanded { border-radius: 24px; }
.island-page.ringing { min-width: 280px; padding-bottom: 12px; }
.lennox-island.ringing { border-radius: 24px; }
.island-ring { color: @primary; }
.lennox-island.timer .island-ring, .lennox-island.timer image { color: #ff9f0a; }
.lennox-island.focus .island-ring, .lennox-island.focus image { color: #30d158; }
.lennox-island.timer .island-detail, .lennox-island.stopwatch .island-detail { color: #ff9f0a; }
.lennox-island.focus .island-detail { color: #30d158; }
.lennox-island.call image, .lennox-island.call .island-detail { color: #0a84ff; }
.lennox-island.glow-red image { color: #ff453a; }
.lennox-island image { color: @primary; }
.lennox-island .island-text { font-weight: 600; font-size: 12px; }
.lennox-island.clock .island-text { font-weight: 700; font-size: 13px; font-feature-settings: "tnum"; }
.lennox-island .island-detail { font-feature-settings: "tnum"; color: @primary; font-weight: 700; font-size: 12px; }
.lennox-island .island-art { border-radius: 5px; }
.island-bar { background-color: @primary; border-radius: 2px; min-width: 3px; }
.island-card { padding-top: 4px; }
.island-cover { border-radius: 10px; }
.island-title { font-weight: 700; font-size: 13px; }
.island-sub { color: alpha(white, 0.6); font-size: 12px; }
.island-big { font-size: 30px; font-weight: 300; font-feature-settings: "tnum"; }
.island-time { font-size: 10px; color: alpha(white, 0.6); font-feature-settings: "tnum"; }
.lennox-island progressbar.island-progress > trough {
    min-height: 4px; border-radius: 99px; border: none; box-shadow: none;
    background-image: none; background-color: alpha(white, 0.22);
}
.lennox-island progressbar.island-progress > trough > progress {
    min-height: 4px; border-radius: 99px; border: none; box-shadow: none;
    background-image: none; background-color: white;
}
.island-button { min-width: 28px; min-height: 28px; padding: 0; border-radius: 99px; border: none; box-shadow: none; background: alpha(white, 0.12); color: white; }
.island-button:hover { background: alpha(white, 0.24); }
.island-button.big { min-width: 34px; min-height: 34px; background: white; color: black; }
.lennox-island .island-button.big image { color: black; }
.island-pill-button { border-radius: 99px; padding: 3px 12px; background: alpha(white, 0.14); color: white; font-weight: 600; font-size: 12px; min-height: 0; }
.island-pill-button:hover { background: alpha(white, 0.26); }
.island-pill-button.stop { background: #ff9f0a; color: black; }
.lennox-island.ringing image { color: #ff9f0a; }
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
