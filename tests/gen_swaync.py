import os
import json
B = "~/.local/bin/"
I = chr

def toggle(icon, text, on_cmd, off_cmd, status_cmd):
    return {
        "label": f"{icon}  {text}",
        "type": "toggle",
        "command": f"sh -c 'if [ \"$SWAYNC_TOGGLE_STATE\" = true ]; then {on_cmd}; else {off_cmd}; fi'",
        "update-command": f"sh -c 'if {status_cmd}; then echo true; else echo false; fi'",
    }

toggles = [
    toggle(I(0xF05A9), "Wi-Fi", "nmcli radio wifi on", "nmcli radio wifi off",
           "[ \"$(nmcli radio wifi)\" = enabled ]"),
    toggle(I(0xF00AF), "Bluetooth", "rfkill unblock bluetooth; sleep 1; bluetoothctl power on", "bluetoothctl power off; rfkill block bluetooth",
           "bluetoothctl show 2>/dev/null | grep -q \"Powered: yes\""),
    toggle(I(0xF036C), "Microphone", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1",
           "! wpctl get-volume @DEFAULT_AUDIO_SOURCE@ | grep -q MUTED"),
    toggle(I(0xF0594), "Night light", f"{B}lennox-nightlight on", f"{B}lennox-nightlight off",
           f"[ \"$({B}lennox-nightlight status)\" = on ]"),
    toggle(I(0xF0297), "Game mode", f"{B}lennox-mode game on", f"{B}lennox-mode game off",
           f"[ \"$({B}lennox-mode game status)\" = on ]"),
    toggle(I(0xF0176), "Stay awake", f"{B}lennox-idle off", f"{B}lennox-idle on",
           f"[ \"$({B}lennox-idle status)\" = off ]"),
    toggle(I(0xF032A), "Battery saver", "powerprofilesctl set power-saver", "powerprofilesctl set balanced",
           "[ \"$(powerprofilesctl get)\" = power-saver ]"),
    toggle(I(0xF050E), "Dark mode", f"{B}lennox-theme dark", f"{B}lennox-theme light",
           f"[ \"$({B}lennox-get appearance.color_mode)\" = dark ]"),
]

actions = [
    {"label": I(0xF0E51), "command": f"sh -c 'sleep 0.5; {B}lennox-screenshot area'"},
    {"label": I(0xF02E9), "command": f"sh -c 'sleep 0.3; {B}lennox-menu wallpaper'"},
    {"label": I(0xF0493), "command": f"{B}lennox-settings"},
    {"label": I(0xF033E), "command": f"sh -c 'sleep 0.3; {B}lennox-power lock'"},
    {"label": I(0xF0425), "command": f"sh -c 'sleep 0.3; {B}lennox-menu power'"},
]

config = {
    "$schema": "/etc/xdg/swaync/configSchema.json",
    "positionX": "right",
    "positionY": "top",
    "layer": "overlay",
    "control-center-layer": "top",
    "layer-shell": True,
    "cssPriority": "user",
    "control-center-width": 400,
    "control-center-margin-top": 10,
    "control-center-margin-bottom": 10,
    "control-center-margin-right": 10,
    "control-center-margin-left": 0,
    "notification-window-width": 380,
    "notification-icon-size": 48,
    "notification-body-image-height": 100,
    "notification-body-image-width": 200,
    "timeout": 5,
    "timeout-low": 3,
    "timeout-critical": 0,
    "fit-to-screen": True,
    "keyboard-shortcuts": True,
    "image-visibility": "when-available",
    "transition-time": 200,
    "hide-on-clear": False,
    "hide-on-action": True,
    "script-fail-notify": True,
    "relative-timestamps": True,
    "notification-grouping": True,
    "text-empty": "No notifications",
    "widgets": [
        "label#greeting",
        "buttons-grid#toggles",
        "volume",
        "slider#mic",
        "slider#brightness",
        "mpris",
        "buttons-grid#actions",
        "dnd",
        "title",
        "notifications",
    ],
    "widget-config": {
        "label#greeting": {"text": "Lennox", "max-lines": 1},
        "buttons-grid#toggles": {"buttons-per-row": 2, "actions": toggles},
        "buttons-grid#actions": {"buttons-per-row": 5, "actions": actions},
        "volume": {"label": I(0xF057E), "show-per-app": True, "show-per-app-icon": True, "show-per-app-label": False, "empty-list-label": "Nothing is playing"},
        "slider#mic": {
            "label": I(0xF036C),
            "cmd_getter": "sh -c \"wpctl get-volume @DEFAULT_AUDIO_SOURCE@ | awk '{print int($2 * 100 + 0.5)}'\"",
            "cmd_setter": "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ $value%",
            "min": 0, "max": 100, "min_limit": 0, "max_limit": 100,
        },
        "slider#brightness": {
            "label": I(0xF00DF),
            "cmd_getter": "sh -c \"brightnessctl -m | head -n1 | cut -d, -f4 | tr -d %\"",
            "cmd_setter": "brightnessctl -q set $value%",
            "min": 0, "max": 100, "min_limit": 5, "max_limit": 100,
        },
        "mpris": {"show-album-art": "when-available", "autohide": True, "loop-carousel": True},
        "dnd": {"text": "Do not disturb"},
        "title": {"text": "Notifications", "clear-all-button": True, "button-text": "Clear all"},
    },
}
out = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/dotfiles/.config/swaync/config.json"
with open(out, "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write("\n")

# validate against the real v0.12.6 schema (structure + allowed keys)
schema = json.load(open(os.environ.get("SP", os.path.dirname(os.path.abspath(__file__))) + "/ref/swaync-schema.json"))
props = schema["properties"]
for k in config:
    assert k in props, f"unknown top-level key {k}"
import re
wprops = schema["widgets"]
for name, cfg in config["widget-config"].items():
    base = name.split("#")[0]
    allowed = wprops[base]["properties"]
    for k in cfg:
        assert k in allowed, f"{name}: unknown key {k}"
    if base == "buttons-grid":
        aprops = allowed["actions"]["items"]["properties"]
        for a in cfg["actions"]:
            for k in a:
                assert k in aprops, f"{name} action: unknown key {k}"
for w in config["widgets"]:
    assert re.match(r"^[a-zA-Z0-9_-]{1,}(#[a-zA-Z0-9_-]{1,}){0,1}?$", w), w
    base=w.split("#")[0]
    assert base in wprops or base=="notifications", base
print("swaync config valid against schema")
