"""UI sounds: soft sounds for notifications, volume keys, screenshots, plugging
in, devices and the lock screen. Lennox Settings > Sound > Sound effects.

    python3 -m lennox.sounds EVENT       play it (if that kind is on)
    python3 -m lennox.sounds list        the events

Sounds come from the freedesktop sound theme (sound-theme-freedesktop).
"""

import os
import subprocess
import sys
import time

from . import settings as S

THEME = "/usr/share/sounds/freedesktop/stereo"
# event: (sound file, the switch in settings["sounds"] that turns it on)
EVENTS = {
    "notification": ("message-new-instant", "notifications"),
    "volume": ("audio-volume-change", "volume_keys"),
    "screenshot": ("camera-shutter", "screenshots"),
    "plug": ("power-plug", "power"),
    "unplug": ("power-unplug", "power"),
    "connect": ("device-added", "devices"),
    "disconnect": ("device-removed", "devices"),
    "lock": ("service-logout", "lock"),
    "login": ("service-login", "login"),
}
GAP = 0.12            # holding a volume key doesn't make a buzz


def sound_file(event, theme=THEME):
    name = EVENTS[event][0]
    for ext in (".oga", ".ogg", ".wav"):
        path = os.path.join(theme, name + ext)
        if os.path.exists(path):
            return path
    return None


def wanted(event, settings, dnd=False):
    """Should this event make a sound right now?"""
    if event not in EVENTS:
        return False
    sounds = settings["sounds"]
    if not sounds["enabled"] or not sounds[EVENTS[event][1]]:
        return False
    # Do not disturb (also focus mode and game mode) silences notifications only
    return not (dnd and event == "notification")


def _dnd():
    try:
        out = subprocess.run(["swaync-client", "-D"], capture_output=True, text=True, timeout=2, check=False)
        return out.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def _too_soon(event):
    stamp = os.path.join(S.RUNTIME_DIR, f"sound-{event}")
    try:
        if time.time() - os.path.getmtime(stamp) < GAP:
            return True
    except OSError:
        pass
    try:
        os.makedirs(S.RUNTIME_DIR, exist_ok=True)
        with open(stamp, "w"):
            pass
    except OSError:
        pass
    return False


def play(event, settings=None):
    """Plays the event's sound in the background; returns True if it started one."""
    settings = settings or S.load()
    if not wanted(event, settings, _dnd() if event == "notification" else False):
        return False
    path = sound_file(event)
    if not path or _too_soon(event):
        return False
    volume = max(0, min(100, settings["sounds"]["volume"])) / 100
    for argv in (["pw-play", f"--volume={volume:.2f}", path], ["paplay", f"--volume={int(volume * 65536)}", path]):
        try:
            subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        except OSError:
            continue
    return False


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    if event == "list":
        print("\n".join(EVENTS))
        return 0
    if event not in EVENTS:
        print(f"usage: lennox-sound-fx {' | '.join(EVENTS)} | list", file=sys.stderr)
        return 2
    play(event)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
