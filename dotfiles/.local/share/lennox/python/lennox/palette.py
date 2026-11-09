"""Command palette: one search box for everything Lennox can do (SUPER + /).

    lennox-palette            open it (rofi)
    lennox-palette list       print every entry (title <TAB> command)

Type a few letters of what you want ("dark", "bar mecha", "fan turbo", "disk",
"wifi"...) and press Enter. Settings pages, bar styles, power and fan modes,
sound packs, color themes, tools and checks are all in one list.
"""

import ast
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.expanduser("~"), ".local", "bin")
SEP = "\t"

# (title, icon, command). Commands are run with the Lennox bin folder first in PATH.
ACTIONS = [
    ("Dark / light mode", "weather-clear-night-symbolic", "lennox-theme toggle"),
    ("Night light on / off", "night-light-symbolic", "lennox-nightlight toggle"),
    ("Game mode on / off", "input-gaming-symbolic", "lennox-mode game toggle"),
    ("Focus mode on / off", "find-location-symbolic", "lennox-focus toggle"),
    ("Pick a wallpaper", "preferences-desktop-wallpaper-symbolic", "lennox-menu wallpaper"),
    ("Random wallpaper", "media-playlist-shuffle-symbolic", "lennox-wallpaper --random"),
    ("Paint the Lennox wallpaper pack", "applications-graphics-symbolic", "lennox-wallpapers make"),
    ("Performance: Quiet", "power-profile-power-saver-symbolic", "lennox-perf quiet"),
    ("Performance: Balanced", "power-profile-balanced-symbolic", "lennox-perf balanced"),
    ("Performance: Max", "power-profile-performance-symbolic", "lennox-perf max"),
    ("Fans: Silent", "weather-clear-symbolic", "lennox-fan set silent"),
    ("Fans: Cool", "weather-few-clouds-symbolic", "lennox-fan set cool"),
    ("Fans: Normal", "weather-overcast-symbolic", "lennox-fan set normal"),
    ("Fans: Turbo (full speed)", "weather-storm-symbolic", "lennox-fan set turbo"),
    ("Clock: timers, alarms, reminders", "alarm-symbolic", "lennox-clock"),
    ("Window overview", "view-grid-symbolic", "lennox-overview"),
    ("Clipboard history", "edit-paste-symbolic", "lennox-menu clipboard"),
    ("Emoji picker", "face-smile-symbolic", "lennox-menu emoji"),
    ("Screenshot an area", "camera-photo-symbolic", "lennox-screenshot area"),
    ("Screenshot the screen", "video-display-symbolic", "lennox-screenshot screen"),
    ("Copy text from the screen (OCR)", "edit-copy-symbolic", "lennox-ocr"),
    ("Pick a color on screen", "color-select-symbolic", "lennox-colorpicker"),
    ("Show all keybindings", "preferences-desktop-keyboard-shortcuts-symbolic", "lennox-menu keybinds"),
    ("Quick panel", "view-more-symbolic", "lennox-panel toggle"),
    ("Dashboard", "view-app-grid-symbolic", "lennox-widgets dashboard"),
    ("Show / hide desktop widgets", "view-app-grid-symbolic", "lennox-widgets desktop"),
    ("Reload the bar", "view-refresh-symbolic", "lennox-bar reload"),
    ("Show / hide the bar", "view-reveal-symbolic", "lennox-bar toggle"),
    ("Show / hide the dock", "view-reveal-symbolic", "lennox-dock toggle"),
    ("Update everything", "software-update-available-symbolic", "lennox-update"),
    ("Disk check (why is my disk read-only?)", "drive-harddisk-symbolic", "kitty --hold lennox-disk check"),
    ("Health check in a terminal", "emblem-ok-symbolic", "kitty --hold lennox-doctor"),
    ("System monitor", "utilities-system-monitor-symbolic", "lennox-open system_monitor"),
    ("Audio mixer", "multimedia-volume-control-symbolic", "lennox-open audio_mixer"),
    ("Terminal", "utilities-terminal-symbolic", "lennox-open terminal"),
    ("Files", "system-file-manager-symbolic", "lennox-open filemanager"),
    ("Browser", "web-browser-symbolic", "lennox-open browser"),
    ("Ask Claude", "dialog-question-symbolic", "lennox-ask"),
    ("Lock the screen", "system-lock-screen-symbolic", "lennox-power lock"),
    ("Sleep", "weather-clear-night-symbolic", "lennox-power suspend"),
    ("Power menu", "system-shutdown-symbolic", "lennox-menu power"),
]

BAR_STYLES = [("lennox", "Islands"), ("lennox-line", "Line"), ("lennox-aurora", "Aurora"), ("lennox-pills", "Pills"),
              ("lennox-dots", "Minimal Dots"), ("lennox-material", "Material"), ("lennox-terminal", "Terminal"),
              ("lennox-mecha", "Mecha"), ("lennox-glow", "Glow"), ("lennox-dock", "Dock"),
              ("modern", "ML4W Modern"), ("glass", "ML4W Glass"), ("minimal", "ML4W Minimal")]

SOUND_PACKS = [("soft", "Soft (marimba)"), ("glass", "Glass (bells)"), ("pop", "Pop (bubbles)"),
               ("freedesktop", "Classic")]


def settings_pages(path=os.path.join(HERE, "app", "main.py")):
    """[(id, title, icon)] read straight from the Settings app (no GTK needed)."""
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PAGES" for t in node.targets):
            try:
                return [(p[0], p[1], p[2]) for p in ast.literal_eval(node.value)]
            except ValueError:
                return []
    return []


def color_themes():
    """[(id, name)] from lennox-theme list ("* id   Name   #color")."""
    try:
        out = subprocess.run([os.path.join(BIN, "lennox-theme"), "list"], capture_output=True, text=True,
                             timeout=5, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    themes = []
    for line in out.splitlines():
        parts = line[2:].split(None, 1) if len(line) > 2 else []
        if len(parts) == 2:
            name = parts[1].rsplit("#", 1)[0].strip()
            themes.append((parts[0], name or parts[0]))
    return themes


def entries(themes=None):
    """Every palette entry: [(title, icon, command)], no duplicate titles."""
    out = list(ACTIONS)
    for page_id, title, icon in settings_pages():
        out.append((f"Settings: {title}", icon, f"lennox-settings --page {page_id}"))
    for style, name in BAR_STYLES:
        out.append((f"Bar style: {name}", "view-grid-symbolic", f"lennox-bar style {style}"))
    for pack, name in SOUND_PACKS:
        out.append((f"Sound pack: {name}", "audio-volume-high-symbolic",
                    f"sh -c 'lennox-set sounds.pack {pack} && lennox-sound-fx notification'"))
    for tid, name in (color_themes() if themes is None else themes):
        out.append((f"Color theme: {name}", "applications-graphics-symbolic", f"lennox-theme set {shlex.quote(tid)}"))
    seen, unique = set(), []
    for item in out:
        if item[0] not in seen:
            seen.add(item[0])
            unique.append(item)
    return unique


def rofi_lines(items):
    return "".join(f"{title}\0icon\x1f{icon}\n" for title, icon, _ in items)


def run(command):
    env = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", ""))
    subprocess.Popen(shlex.split(command), env=env, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv):
    items = entries()
    if len(argv) > 1 and argv[1] == "list":
        for title, _icon, command in items:
            print(f"{title}{SEP}{command}")
        return 0
    if subprocess.run(["pgrep", "-x", "rofi"], capture_output=True, check=False).returncode == 0:
        subprocess.run(["pkill", "-x", "rofi"], check=False)      # the shortcut again closes it
        return 0
    rofi = ["rofi", "-dmenu", "-i", "-p", "  Lennox", "-format", "i", "-no-custom", "-matching", "fuzzy",
            "-config", os.path.expanduser("~/.config/rofi/compact.rasi"),
            "-mesg", "Settings, bar styles, modes, fans, sounds, themes, tools: type what you want"]
    try:
        picked = subprocess.run(rofi, input=rofi_lines(items), capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        print("lennox-palette: rofi is missing", file=sys.stderr)
        return 1
    if picked.isdigit() and int(picked) < len(items):
        run(items[int(picked)][2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
