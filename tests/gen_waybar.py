import os
import json, os
B = "~/.local/bin/"
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/dotfiles/.config/waybar"
I = lambda cp: chr(cp)

modules = {}

# Workspaces: ten custom modules fed by lennox-workspaces (see that script)
for n in range(1, 11):
    modules[f"custom/ws{n}"] = {
        "exec": f"{B}lennox-ws {n}",
        "return-type": "json",
        "interval": "once",
        "signal": 8,
        "format": "{text}",
        "on-click": f"{B}lennox-ws go {n}",
        "on-scroll-up": f"{B}lennox-ws prev",
        "on-scroll-down": f"{B}lennox-ws next",
    }
modules["group/workspaces"] = {
    "orientation": "inherit",
    "modules": [f"custom/ws{n}" for n in range(1, 11)],
}

modules["hyprland/window"] = {
    "max-length": 60,
    "separate-outputs": True,
    "rewrite": {
        "(.*) — Zen Browser": "$1",
        "(.*) - Zen Browser": "$1",
        "(.*) — Mozilla Firefox": "$1",
        "(.*) - Visual Studio Code": "$1",
        "(.*) - Code - OSS": "$1",
    },
}

modules["custom/appmenu"] = {
    "format": "Apps",
    "on-click": f"{B}lennox-menu apps",
    "on-click-right": f"{B}lennox-menu keybinds",
    "tooltip-format": "Left: Open the app launcher\nRight: Show all keybindings",
}
modules["custom/appmenuicon"] = {
    "format": I(0xF003B),
    "on-click": f"{B}lennox-menu apps",
    "on-click-right": f"{B}lennox-menu keybinds",
    "tooltip-format": "Left: Open the app launcher\nRight: Show all keybindings",
}

modules["custom/updates"] = {
    "format": I(0xF03D7) + "  {text}",
    "return-type": "json",
    "exec": f"{B}lennox-updates waybar",
    "interval": 1800,
    "signal": 12,
    "on-click": f"{B}lennox-update",
    "on-click-right": f"{B}lennox-updates refresh",
}

modules["pulseaudio"] = {
    "format": "{icon}  {volume}%",
    "format-bluetooth": "{icon} " + I(0xF00AF) + "  {volume}%",
    "format-muted": I(0xF0581) + "  muted",
    "format-icons": {
        "headphone": I(0xF02CB),
        "headset": I(0xF02CE),
        "default": [I(0xF057F), I(0xF0580), I(0xF057E)],
    },
    "scroll-step": 5,
    "max-volume": 100,
    "on-click": f"{B}lennox-open audio_mixer",
    "on-click-right": f"{B}lennox-osd volume mute",
    "on-click-middle": f"{B}lennox-osd mic mute",
    "tooltip-format": "{desc}\nLeft: Sound settings\nRight: Mute\nMiddle: Mute microphone",
}

modules["bluetooth"] = {
    "format": I(0xF00AF),
    "format-connected": I(0xF00B1) + " {num_connections}",
    "format-disabled": I(0xF00B2),
    "format-off": I(0xF00B2),
    "format-no-controller": "",
    "interval": 30,
    "on-click": "blueman-manager",
    "tooltip-format": "Bluetooth: {status}",
    "tooltip-format-connected": "Connected:\n{device_enumerate}",
    "tooltip-format-enumerate-connected": "{device_alias}",
    "tooltip-format-enumerate-connected-battery": "{device_alias}  {device_battery_percentage}%",
}

modules["network"] = {
    "format": "{ifname}",
    "format-wifi": I(0xF05A9) + "  {signalStrength}%",
    "format-ethernet": I(0xF0200) + "  wired",
    "format-disconnected": I(0xF05AA) + "  offline",
    "tooltip-format-wifi": "{essid} ({signalStrength}%)\nIP: {ipaddr}\nDown {bandwidthDownBits}  Up {bandwidthUpBits}\nLeft: Wi-Fi networks  Right: Network settings",
    "tooltip-format-ethernet": "{ifname}\nIP: {ipaddr}\nDown {bandwidthDownBits}  Up {bandwidthUpBits}",
    "tooltip-format-disconnected": "Not connected\nLeft: Wi-Fi networks",
    "max-length": 40,
    "on-click": f"{B}lennox-menu wifi",
    "on-click-right": "nm-connection-editor",
}

modules["battery"] = {
    "interval": 10,
    "states": {"warning": 25, "critical": 12},
    "format": "{icon}  {capacity}%",
    "format-charging": I(0xF0084) + "  {capacity}%",
    "format-plugged": I(0xF06A5) + "  {capacity}%",
    "format-full": I(0xF0079) + "  full",
    "format-icons": [I(c) for c in (0xF007A, 0xF007B, 0xF007C, 0xF007D, 0xF007E, 0xF007F, 0xF0080, 0xF0081, 0xF0082, 0xF0079)],
    "tooltip-format": "{timeTo}\n{power:.1f} W",
}

modules["power-profiles-daemon"] = {
    "format": "{icon}",
    "tooltip-format": "Power profile: {profile}\nClick to change",
    "format-icons": {
        "default": I(0xF04C5),
        "performance": I(0xF04C5),
        "balanced": I(0xF05D1),
        "power-saver": I(0xF032A),
    },
}

# Hardware drawer
modules["custom/system"] = {"format": I(0xF061A), "tooltip": False}
modules["cpu"] = {"format": I(0xF0EE0) + " {usage}%", "interval": 5, "on-click": f"{B}lennox-open system_monitor"}
modules["memory"] = {"format": I(0xF035B) + " {percentage}%", "interval": 10, "on-click": f"{B}lennox-open system_monitor"}
modules["disk"] = {"format": I(0xF02CA) + " {percentage_used}%", "interval": 60, "path": "/", "on-click": f"{B}lennox-open system_monitor"}
modules["custom/gpu"] = {
    "exec": f"{B}lennox-gpu waybar",
    "return-type": "json",
    "interval": 15,
    "format": "{text}",
    "on-click": f"{B}lennox-settings --page graphics",
}
modules["hyprland/language"] = {"format": I(0xF030C) + " {short}"}
modules["group/hardware"] = {
    "orientation": "inherit",
    "drawer": {"transition-duration": 300, "children-class": "drawer-child", "transition-left-to-right": False},
    "modules": ["custom/system", "disk", "cpu", "memory", "custom/gpu", "hyprland/language"],
}

# Tools drawer
modules["custom/tools"] = {"format": I(0xF1064), "tooltip-format": "Tools"}
modules["custom/cliphist"] = {
    "format": I(0xF0A38),
    "on-click": f"{B}lennox-menu clipboard",
    "on-click-right": f"{B}lennox-menu clipboard-clear",
    "tooltip-format": "Left: Clipboard history\nRight: Clear history",
}
modules["custom/idle"] = {
    "exec": f"{B}lennox-idle waybar",
    "return-type": "json",
    "interval": 60,
    "signal": 11,
    "format": "{text}",
    "on-click": f"{B}lennox-idle toggle",
}
modules["custom/nightlight"] = {
    "exec": f"{B}lennox-nightlight waybar",
    "return-type": "json",
    "interval": 60,
    "signal": 9,
    "format": "{text}",
    "on-click": f"{B}lennox-nightlight toggle",
}
modules["custom/gamemode"] = {
    "exec": f"{B}lennox-mode game waybar",
    "return-type": "json",
    "interval": "once",
    "signal": 10,
    "format": "{text}",
    "on-click": f"{B}lennox-mode game toggle",
}
modules["group/tools"] = {
    "orientation": "inherit",
    "drawer": {"transition-duration": 300, "children-class": "drawer-child", "transition-left-to-right": False},
    "modules": ["custom/tools", "custom/cliphist", "custom/idle", "custom/nightlight", "custom/gamemode", "power-profiles-daemon"],
}

modules["tray"] = {"icon-size": 18, "spacing": 10}

modules["custom/notification"] = {
    "format": "{icon}",
    "format-icons": {
        "notification": I(0xF116B),
        "none": I(0xF009A),
        "dnd-notification": I(0xF00A0),
        "dnd-none": I(0xF00A0),
        "inhibited-notification": I(0xF116B),
        "inhibited-none": I(0xF009A),
        "dnd-inhibited-notification": I(0xF00A0),
        "dnd-inhibited-none": I(0xF00A0),
    },
    "return-type": "json",
    "exec-if": "which swaync-client",
    "exec": "swaync-client -swb",
    "on-click": f"{B}lennox-panel toggle",
    "on-click-right": "swaync-client -d -sw",
    "tooltip-format": "Left: Quick panel\nRight: Do not disturb",
    "escape": True,
}

modules["custom/exit"] = {
    "format": I(0xF0425),
    "on-click": f"{B}lennox-menu power",
    "tooltip-format": "Power menu",
}

modules["custom/lennox"] = {
    "format": " ",
    "on-click": f"{B}lennox-panel toggle",
    "on-click-right": f"{B}lennox-settings",
    "tooltip-format": "Left: Quick panel\nRight: Lennox Settings",
}

modules["mpris"] = {
    "format": "{status_icon}  {title}",
    "format-paused": "{status_icon}  <i>{title}</i>",
    "status-icons": {"playing": I(0xF040A), "paused": I(0xF03E4), "stopped": I(0xF075A)},
    "max-length": 40,
    "on-click-right": "playerctl next",
    "tooltip-format": "{artist} - {title}\nLeft: Play / pause  Right: Next",
}

# clock formats are filled in by lennox-bar (12h / 24h setting)
modules["clock"] = {
    "format": "{:%H:%M  %a}",
    "format-alt": "{:%A %d %B %Y}",
    "tooltip-format": "<tt><small>{calendar}</small></tt>",
    "calendar": {
        "mode": "month",
        "weeks-pos": "",
        "on-scroll": 1,
        "format": {"today": "<b><u>{}</u></b>"},
    },
    "actions": {"on-scroll-up": "shift_up", "on-scroll-down": "shift_down"},
}

with open(os.path.join(root, "modules.json"), "w") as f:
    json.dump(modules, f, indent=2, ensure_ascii=False)
    f.write("\n")

base = {"layer": "top", "position": "top", "margin-top": 0, "margin-bottom": 0, "margin-left": 0, "margin-right": 0, "spacing": 0, "reload_style_on_change": False}
right_common = ["custom/updates", "pulseaudio", "bluetooth", "network", "battery", "group/hardware", "group/tools", "tray", "custom/notification", "custom/exit", "custom/lennox"]
themes = {
    "modern": {
        "name": "Modern",
        "modules-left": ["custom/appmenu", "group/workspaces"],
        "modules-center": ["hyprland/window"],
        "modules-right": right_common + ["clock"],
    },
    "glass": {
        "name": "Glass",
        "modules-left": ["custom/appmenu", "group/workspaces"],
        "modules-center": ["clock"],
        "modules-right": right_common,
    },
    "minimal": {
        "name": "Minimal",
        "modules-left": ["custom/appmenuicon", "group/workspaces"],
        "modules-center": ["hyprland/window"],
        "modules-right": ["custom/updates", "pulseaudio", "bluetooth", "network", "battery", "power-profiles-daemon", "group/hardware", "group/tools", "custom/exit", "clock", "tray", "custom/notification", "custom/lennox"],
    },
}
for key, t in themes.items():
    cfg = dict(base)
    cfg["modules-left"] = t["modules-left"]
    cfg["modules-center"] = t["modules-center"]
    cfg["modules-right"] = t["modules-right"]
    with open(os.path.join(root, "themes", key, "config.json"), "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
print("ok", len(modules))
