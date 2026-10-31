"""Lennox settings: one JSON file, merged over safe defaults.

~/.config/lennox/settings.json is the single source of truth. Everything
else (Hyprland's settings.lua, hypridle.conf, hyprsunset.conf, GTK
settings, ...) is generated from it by `lennox-apply`.
"""

import copy
import json
import os
import tempfile

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")), "lennox")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "lennox")
STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.join(HOME, ".local", "state")), "lennox")
RUNTIME_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "lennox")

DEFAULTS = {
    "appearance": {
        "color_mode": "dark",
        "theme": "wallpaper",
        "color_scheme": "scheme-tonal-spot",
        "animations": "default",
        "border_style": "gradient",
        "workspace_anim": "preset",
        "gaps_in": 8,
        "gaps_out": 14,
        "border_size": 2,
        "rounding": 14,
        "active_opacity": 1.0,
        "inactive_opacity": 0.9,
        "blur": True,
        "blur_size": 5,
        "blur_passes": 4,
        "shadow": True,
        "dim_inactive": False,
        "layout": "dwindle",
        "window_mode": "tiling",
        "font": "Fira Sans Semibold 11",
        "icon_theme": "Papirus-Dark",
        "cursor_theme": "Bibata-Modern-Ice",
        "cursor_size": 24,
        "terminal_opacity": 0.8,
    },
    "wallpaper": {
        "folder": "~/.config/lennox/wallpapers",
        "transition": "grow",
        "lockscreen_blur": "50x30",
        "auto_change_minutes": 0,
        "live_pause_battery": True,    # live (video) wallpaper: a still picture on battery
    },
    "bar": {
        "enabled": True,
        "style": "lennox",
        "show_window_title": True,
        "show_hardware": True,
        "show_tray": True,
        "show_updates": True,
        "show_media": False,
        "clock_24h": True,
    },
    "widgets": {
        "desktop": True,
        "position": "top-left",
        "show_clock": True,
        "show_greeting": True,
        "show_weather": True,
        "show_media": True,
        "show_system": False,
        "name": "",
        "weather_city": "",
        "temperature_unit": "celsius",
        "island": True,                # the dynamic island
        "island_place": "bar",         # bar: in the middle of the bar (it's the clock) | below
        "island_music": True,
        "island_notifications": True,
    },
    "dock": {
        "enabled": True,
        "autohide": True,
        "icon_size": 40,
    },
    "display": {
        "scale": 1.0,
    },
    "input": {
        "kb_layout": "us",
        "kb_variant": "",
        "kb_model": "",
        "kb_options": "grp:alt_shift_toggle",
        "repeat_rate": 35,
        "repeat_delay": 300,
        "numlock": True,
        "sensitivity": 0.0,
        "accel_profile": "",
        "natural_scroll": False,
        "follow_mouse": 1,
    },
    "touchpad": {
        "natural_scroll": True,
        "tap_to_click": True,
        "tap_and_drag": True,
        "disable_while_typing": True,
        "clickfinger": False,
        "middle_button_emulation": False,
        "scroll_factor": 1.0,
        "gestures": True,
    },
    "keybinds": {
        "main_mod": "SUPER",
    },
    "idle": {
        "dim_minutes": 8,
        "lock_minutes": 10,
        "screen_off_minutes": 11,
        "suspend_minutes": 30,
        "suspend_on_ac": False,
        "lock_before_sleep": True,
    },
    "night": {
        "nightlight": True,
        "start": "20:00",
        "end": "07:00",
        "temperature": 4500,
        "winddown": True,
        "winddown_time": "23:00",
        "winddown_message": "Wind-down time. Sleep is free gains, so wrap up when you're ready.",
        "winddown_dim": True,          # warmer, dimmer screen over 30 minutes
        "winddown_quiet": True,        # do not disturb until the night light ends
        "winddown_reminders": True,    # at bedtime, again 30 minutes later
        "sleep_stats": True,           # when you really stopped, weekly summary
        "smart_bedtime": False,        # move the bedtime by itself each week (toward the goal)
        "bedtime_goal": "23:00",       # the bedtime smart bedtime works toward
    },
    "clips": {
        "mode": "gaming",              # gaming: only while a game runs | always | off
        "seconds": 120,                # how much SUPER + ALT + R saves
        "folder": "~/Videos/Clips",
        "mic": False,                  # also record your microphone
    },
    "games": {
        "overlay": "hidden",           # FPS overlay (MangoHud): hidden until Shift + F12 | shown
        "mc_server": "vetosmp.net",    # Minecraft server in the bar ("" = off)
        "mc_joins": True,              # notify when someone joins
    },
    "ai": {
        "spend_widget": True,          # AI coding spend in the bar (CodeBurn)
        "monthly_budget": 200,         # warn at 80% and 100%; 0 = no warnings
    },
    "lockscreen": {
        "widgets": True,               # lines bottom left on the lock screen
        "music": True,
        "alarm": True,                 # next alarm, timer or reminder
        "weather": True,
        "phone": True,                 # phone battery (KDE Connect)
        "server": True,                # Minecraft server players
    },
    "sounds": {
        "enabled": True,               # UI sounds (Lennox Settings > Sound > Sound effects)
        "volume": 60,
        "notifications": True,         # not in Do not disturb, focus or game mode
        "volume_keys": True,
        "screenshots": True,
        "power": True,                 # plugging in / unplugging the charger
        "devices": True,               # Bluetooth devices connecting
        "lock": True,
        "login": False,
    },
    "focus": {
        "minutes": 50,                 # a focus session
        "break_minutes": 5,            # the break after it (0 = none)
        "rounds": 1,                   # Pomodoro: focus + break repeated this many times (1 = one session)
        "long_break_minutes": 15,      # the break after the last round of a set
        "block_apps": "vesktop, discord, steam",          # closed while focusing (app names)
        "block_sites": "youtube.com, tiktok.com, instagram.com, reddit.com, x.com, twitch.tv",
        "quiet": True,                 # notifications wait in the panel
        "sound": True,                 # a soft sound at the end of focus and of the break
    },
    "backup": {
        "folder": "",                  # where backups go (a drive that survives a reinstall)
        "weekly": False,               # back up every week (needs a folder)
        "keep": 5,                     # how many backups to keep
    },
    "cleanup": {
        "weekly": True,                # every week: old trash, thumbnails, AUR build files
        "trash_days": 30,              # trash older than this goes (0 = empty it all)
    },
    "power": {
        "saver_on_battery": True,
        "low_battery_warning": 20,
        "critical_battery": 8,
    },
    "apps": {
        "terminal": "kitty",
        "browser": "flatpak run app.zen_browser.zen",
        "filemanager": "nautilus",
        "editor": "code",
        "calculator": "gnome-calculator",
        "system_monitor": "missioncenter",
        "audio_mixer": "pavucontrol",
    },
    "gpu": {
        "mode": "auto",
    },
    "welcome": {
        "show_on_login": True,
    },
}

# Allowed values for settings with a fixed set of choices
CHOICES = {
    ("appearance", "color_mode"): ["dark", "light"],
    ("appearance", "theme"): None,  # filled from THEMES below
    ("appearance", "color_scheme"): [
        "scheme-tonal-spot", "scheme-content", "scheme-expressive", "scheme-fidelity",
        "scheme-fruit-salad", "scheme-monochrome", "scheme-neutral", "scheme-rainbow",
        "scheme-vibrant",
    ],
    ("appearance", "animations"): ["default", "dynamic", "moving", "classic", "fast", "smooth", "bouncy", "off"],
    ("appearance", "border_style"): ["gradient", "animated", "solid", "none"],
    ("appearance", "workspace_anim"): ["preset", "slide", "slidevert", "fade", "slidefade"],
    ("appearance", "layout"): ["dwindle", "master"],
    ("appearance", "window_mode"): ["tiling", "stacking"],
    ("wallpaper", "transition"): ["grow", "fade", "wipe", "wave", "outer", "center", "any", "simple", "none"],
    ("bar", "style"): ["lennox", "lennox-line", "modern", "glass", "minimal"],
    ("widgets", "position"): ["top-left", "top-center", "top-right", "center", "bottom-left", "bottom-right"],
    ("widgets", "temperature_unit"): ["celsius", "fahrenheit"],
    ("clips", "mode"): ["gaming", "always", "off"],
    ("widgets", "island_place"): ["bar", "below"],
    ("games", "overlay"): ["hidden", "shown"],
    ("input", "accel_profile"): ["", "adaptive", "flat"],
    ("keybinds", "main_mod"): ["SUPER", "ALT"],
    ("gpu", "mode"): ["auto", "integrated", "hybrid"],
}

# Inclusive ranges for numeric settings
RANGES = {
    ("appearance", "gaps_in"): (0, 40),
    ("appearance", "gaps_out"): (0, 60),
    ("appearance", "border_size"): (0, 8),
    ("appearance", "rounding"): (0, 30),
    ("appearance", "active_opacity"): (0.5, 1.0),
    ("appearance", "inactive_opacity"): (0.5, 1.0),
    ("appearance", "blur_size"): (1, 12),
    ("appearance", "blur_passes"): (1, 6),
    ("appearance", "cursor_size"): (16, 64),
    ("appearance", "terminal_opacity"): (0.5, 1.0),
    ("wallpaper", "auto_change_minutes"): (0, 1440),
    ("dock", "icon_size"): (24, 64),
    ("display", "scale"): (0.5, 3.0),
    ("input", "repeat_rate"): (10, 80),
    ("input", "repeat_delay"): (150, 1000),
    ("input", "sensitivity"): (-1.0, 1.0),
    ("input", "follow_mouse"): (0, 3),
    ("touchpad", "scroll_factor"): (0.1, 3.0),
    ("idle", "dim_minutes"): (0, 240),
    ("idle", "lock_minutes"): (0, 240),
    ("idle", "screen_off_minutes"): (0, 240),
    ("idle", "suspend_minutes"): (0, 480),
    ("night", "temperature"): (2500, 6000),
    ("ai", "monthly_budget"): (0, 100000),
    ("clips", "seconds"): (10, 600),
    ("cleanup", "trash_days"): (0, 365),
    ("backup", "keep"): (1, 50),
    ("focus", "minutes"): (5, 240),
    ("sounds", "volume"): (0, 100),
    ("focus", "break_minutes"): (0, 60),
    ("focus", "long_break_minutes"): (0, 90),
    ("focus", "rounds"): (1, 8),
    ("power", "low_battery_warning"): (5, 50),
    ("power", "critical_battery"): (2, 20),
}

# Color themes: every color on the desktop is built from one base color
# (matugen), instead of from the wallpaper. id: (name, base color, scheme
# override or None to use your Color style)
THEMES = {
    "wallpaper": ("From your wallpaper", None, None),
    "ocean": ("Ocean", "#2f7fd6", None),
    "aqua": ("Aqua", "#1fb5a8", None),
    "forest": ("Forest", "#4f9a5e", None),
    "lime": ("Lime", "#8bc34a", None),
    "gold": ("Gold", "#d9a441", None),
    "sunset": ("Sunset", "#f0803c", None),
    "crimson": ("Crimson", "#d1495b", None),
    "sakura": ("Sakura", "#e889b0", None),
    "lavender": ("Lavender", "#9d7cd8", None),
    "midnight": ("Midnight", "#3d4f9c", None),
    "graphite": ("Graphite", "#7a7a7a", "scheme-monochrome"),
}
CHOICES[("appearance", "theme")] = list(THEMES)

# One-click looks (Lennox Settings > Appearance, or `lennox look NAME`).
# Each sets several values at once; everything else stays as it is.
_BASE_LOOK = {
    "appearance.border_style": "gradient", "appearance.border_size": 2, "appearance.rounding": 14,
    "appearance.gaps_in": 8, "appearance.gaps_out": 14, "appearance.blur": True,
    "appearance.blur_size": 5, "appearance.shadow": True, "appearance.inactive_opacity": 0.9,
    "appearance.dim_inactive": False, "appearance.animations": "default",
    "appearance.workspace_anim": "preset", "appearance.terminal_opacity": 0.8,
    "bar.style": "lennox",
}
LOOKS = {
    "lennox": ("Lennox", "Glass islands, soft corners and smooth motion", dict(_BASE_LOOK, **{
        "appearance.color_scheme": "scheme-tonal-spot"})),
    "glass": ("Glass", "Extra see-through and frosted", dict(_BASE_LOOK, **{
        "appearance.border_size": 1, "appearance.rounding": 18, "appearance.blur_size": 7,
        "appearance.inactive_opacity": 0.82, "appearance.terminal_opacity": 0.7,
        "appearance.animations": "smooth"})),
    "neon": ("Neon", "Vibrant colors and a spinning border", dict(_BASE_LOOK, **{
        "appearance.color_scheme": "scheme-vibrant", "appearance.border_style": "animated",
        "appearance.border_size": 3, "appearance.animations": "dynamic"})),
    "minimal": ("Minimal", "One slim bar, small gaps, quick motion", dict(_BASE_LOOK, **{
        "appearance.border_style": "solid", "appearance.border_size": 1, "appearance.rounding": 10,
        "appearance.gaps_in": 4, "appearance.gaps_out": 8, "appearance.blur": False,
        "appearance.shadow": False, "appearance.inactive_opacity": 1.0, "appearance.animations": "fast",
        "appearance.terminal_opacity": 0.95, "bar.style": "lennox-line"})),
    "focus": ("Focus", "Dims everything except the window you work in", dict(_BASE_LOOK, **{
        "appearance.color_scheme": "scheme-neutral", "appearance.border_style": "solid",
        "appearance.gaps_in": 6, "appearance.gaps_out": 10, "appearance.dim_inactive": True,
        "appearance.inactive_opacity": 0.8, "appearance.animations": "smooth", "bar.style": "lennox-line"})),
    "lightweight": ("Lightweight", "No blur or shadows, quick animations: smoothest on battery", dict(_BASE_LOOK, **{
        "appearance.border_style": "solid", "appearance.blur": False, "appearance.shadow": False,
        "appearance.inactive_opacity": 1.0, "appearance.animations": "fast",
        "appearance.terminal_opacity": 1.0, "bar.style": "lennox-line"})),
    "ml4w": ("ML4W Classic", "The original ML4W style, if you miss it", dict(_BASE_LOOK, **{
        "appearance.rounding": 10, "appearance.gaps_in": 10, "appearance.gaps_out": 16,
        "appearance.blur_size": 4, "bar.style": "modern"})),
}

TIME_KEYS = {("night", "start"), ("night", "end"), ("night", "winddown_time"), ("night", "bedtime_goal")}

# Which `lennox-apply` part(s) must run after a setting in a section changes
APPLY_PARTS = {
    "appearance": ["hypr", "gtk"],
    "display": ["hypr"],
    "input": ["hypr"],
    "touchpad": ["hypr"],
    "keybinds": ["hypr"],
    "idle": ["idle"],
    "night": ["night"],
    "wallpaper": ["wallpaper"],
    "bar": ["bar"],
    "dock": ["dock"],
    "widgets": ["widgets"],
    "ai": ["aispend"],
    "games": ["games"],
    "cleanup": ["cleanup"],
    "backup": ["backup"],
}
THEME_KEYS = {"appearance.color_mode", "appearance.color_scheme", "appearance.theme"}


def parts_for(path):
    """lennox-apply parts to run after the setting at `path` changed."""
    if path in THEME_KEYS:
        return ["theme"]
    return APPLY_PARTS.get(path.partition(".")[0], [])


def _valid_time(value):
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return False
    return 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59


def _same_type(default, value):
    # bool is a subclass of int, so check it first
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float))
    return isinstance(value, type(default))


def _clean(section, key, default, value):
    """Return `value` if it is valid for this setting, otherwise `default`."""
    if not _same_type(default, value):
        return default
    if (section, key) in CHOICES and value not in CHOICES[(section, key)]:
        return default
    if (section, key) in RANGES:
        low, high = RANGES[(section, key)]
        value = min(max(value, low), high)
        if isinstance(default, int) and not isinstance(default, bool):
            value = int(round(value))
    if (section, key) in TIME_KEYS and not _valid_time(value):
        return default
    if isinstance(value, float):
        value = round(value, 3)
    return value


def merge(data):
    """Merge user data over the defaults, dropping anything invalid."""
    result = copy.deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        return result
    for section, values in DEFAULTS.items():
        user_section = data.get(section)
        if not isinstance(user_section, dict):
            continue
        for key, default in values.items():
            if key in user_section:
                result[section][key] = _clean(section, key, default, user_section[key])
    return result


def load():
    """Load settings.json; a missing or broken file gives the defaults."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return merge(data)


def save(settings):
    """Validate and atomically write settings.json."""
    clean = merge(settings)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, SETTINGS_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return clean


def get(settings, path):
    """Get a value by dotted path, e.g. get(s, "bar.style")."""
    section, _, key = path.partition(".")
    if section not in settings or key not in settings[section]:
        raise KeyError(path)
    return settings[section][key]


def parse_value(path, text):
    """Convert command line text to the type of the setting at `path`."""
    section, _, key = path.partition(".")
    if section not in DEFAULTS or key not in DEFAULTS[section]:
        raise KeyError(path)
    default = DEFAULTS[section][key]
    if isinstance(default, bool):
        lowered = text.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
        raise ValueError(f"{path} must be true or false")
    key_tuple = (section, key)
    if isinstance(default, int):
        value = int(float(text))
    elif isinstance(default, float):
        value = float(text)
    else:
        value = text
    if key_tuple in CHOICES and value not in CHOICES[key_tuple]:
        options = " | ".join(repr(c) if c == "" else str(c) for c in CHOICES[key_tuple])
        raise ValueError(f"{path} must be one of: {options}")
    return value


def set_value(path, value):
    """Load, change one value, save. Returns the saved value."""
    settings = load()
    section, _, key = path.partition(".")
    if section not in settings or key not in settings[section]:
        raise KeyError(path)
    settings[section][key] = value
    saved = save(settings)
    return saved[section][key]


def expand(path):
    """Expand ~ and $HOME in a path setting."""
    return os.path.expanduser(os.path.expandvars(path))


def apply_look(name):
    """Apply a look from LOOKS. Returns the lennox-apply parts to run."""
    _title, _desc, values = LOOKS[name]
    settings = load()
    for path, value in values.items():
        section, _, key = path.partition(".")
        settings[section][key] = value
    save(settings)
    parts = []
    for path in values:
        for part in parts_for(path):
            if part not in parts:
                parts.append(part)
    return parts
