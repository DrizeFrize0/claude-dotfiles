"""UI sounds: soft sounds for notifications, volume keys, screenshots, plugging
in, devices and the lock screen. Lennox Settings > Sound > Sound effects.

    python3 -m lennox.sounds EVENT       play it (if that kind is on)
    python3 -m lennox.sounds list        the events

    python3 -m lennox.sounds make [PACK]   (re)build a sound pack

Packs: "soft" (warm marimba, the default), "glass" (small bells), "pop" (bubbly) are
synthesized on this machine the first time they are needed, in pure Python;
"freedesktop" uses the system's sound theme (sound-theme-freedesktop).
"""

import math
import os
import random
import struct
import subprocess
import sys
import time
import wave

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
PACKS = ("soft", "glass", "pop", "freedesktop")
PACK_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "lennox", "sounds")
RATE = 44100

# ---------------------------------------------------------------- the synthesizer
# Each pack is a timbre; each event a tiny motif of (note, start seconds, length, loudness).
# Notes as semitones from A4 (440 Hz).
MOTIFS = {
    "notification": [(7, 0.0, 0.5, 0.8), (12, 0.09, 0.7, 0.7)],          # E5 -> A5, a friendly "ding-dong" up
    "volume": [(19, 0.0, 0.07, 0.5)],                                      # a tiny tick
    "screenshot": "shutter",
    "plug": [(3, 0.0, 0.35, 0.6), (7, 0.07, 0.35, 0.6), (10, 0.14, 0.6, 0.7)],    # rising C-E-G
    "unplug": [(10, 0.0, 0.35, 0.6), (7, 0.07, 0.35, 0.6), (3, 0.14, 0.6, 0.6)],  # falling
    "connect": [(5, 0.0, 0.3, 0.6), (12, 0.08, 0.5, 0.65)],
    "disconnect": [(12, 0.0, 0.3, 0.6), (5, 0.08, 0.5, 0.55)],
    "lock": [(0, 0.0, 0.6, 0.55), (-5, 0.12, 0.9, 0.5)],                   # low and calm, going down
    "login": [(-9, 0.0, 1.2, 0.45), (-5, 0.08, 1.2, 0.45), (-2, 0.16, 1.2, 0.45), (3, 0.24, 1.4, 0.5)],
}

# timbre: [(partial ratio, level, decay per second)], attack seconds, pitch glide
TIMBRES = {
    "soft": ([(1.0, 1.0, 7.0), (4.0, 0.25, 22.0), (9.2, 0.06, 40.0)], 0.004, 0.0),     # marimba
    "glass": ([(1.0, 0.8, 3.2), (2.76, 0.35, 5.0), (5.4, 0.18, 8.0), (8.93, 0.08, 12.0)], 0.002, 0.0),  # bell
    "pop": ([(1.0, 1.0, 14.0), (2.0, 0.2, 30.0)], 0.003, 0.45),                          # bubble: pitch slides up
}


def _note(samples, semitone, start, length, loud, timbre):
    partials, attack, glide = timbre
    f0 = 440.0 * 2 ** (semitone / 12)
    begin = int(start * RATE)
    for i in range(int(length * RATE)):
        t = i / RATE
        env = min(1.0, t / attack) if attack else 1.0
        freq = f0 * (1 + glide * min(t / 0.06, 1.0)) if glide else f0
        value = 0.0
        for ratio, level, decay in partials:
            value += level * math.exp(-decay * t) * math.sin(2 * math.pi * freq * ratio * t)
        j = begin + i
        if j < len(samples):
            samples[j] += value * env * loud


def _shutter(samples, timbre):
    rnd = random.Random(7)
    low = 0.0
    for start in (0.0, 0.06):                       # two clicks: the shutter opening and closing
        begin = int(start * RATE)
        for i in range(int(0.05 * RATE)):
            t = i / RATE
            low += 0.35 * (rnd.uniform(-1, 1) - low)   # soft, filtered noise
            j = begin + i
            if j < len(samples):
                samples[j] += low * math.exp(-70 * t) * 1.4 * min(1.0, t / 0.001)
    _note(samples, 24, 0.0, 0.08, 0.15, timbre)    # a little sparkle on top


def synth(event, pack):
    """The event's sound in this pack as 16-bit mono samples (a list of ints)."""
    timbre = TIMBRES[pack]
    motif = MOTIFS[event]
    length = 0.25 if motif == "shutter" else max(start + dur for _, start, dur, _ in motif) + 0.05
    samples = [0.0] * int(length * RATE)
    if motif == "shutter":
        _shutter(samples, timbre)
    else:
        for semitone, start, dur, loud in motif:
            _note(samples, semitone, start, dur, loud, timbre)
    peak = max(1e-9, max(abs(v) for v in samples))
    fade = int(0.02 * RATE)                          # no click at the end
    out = []
    for i, v in enumerate(samples):
        if i >= len(samples) - fade:
            v *= (len(samples) - i) / fade
        out.append(int(v / peak * 0.7 * 32767))
    return out


def make_pack(pack, folder=None):
    """Write every event's sound for this pack; returns the folder."""
    folder = os.path.join(folder or PACK_DIR, pack)
    os.makedirs(folder, exist_ok=True)
    for event in EVENTS:
        path = os.path.join(folder, event + ".wav")
        with wave.open(path + ".tmp", "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            data = synth(event, pack)
            w.writeframes(struct.pack("<%dh" % len(data), *data))
        os.replace(path + ".tmp", path)
    return folder


def sound_file(event, theme=THEME, pack="freedesktop", folder=None):
    """The file to play: the pack's (built on first use), or the system theme's."""
    if pack in TIMBRES:
        path = os.path.join(folder or PACK_DIR, pack, event + ".wav")
        if not os.path.exists(path):
            try:
                make_pack(pack, folder)
            except OSError:
                path = None
        if path and os.path.exists(path):
            return path
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
    # Quiet at night: no effects during the sleep wind-down
    if os.path.exists(os.path.join(S.RUNTIME_DIR, "winddown-active")):
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
    path = sound_file(event, pack=settings["sounds"].get("pack", "soft"))
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
    if event == "make":
        packs = argv[2:] or [p for p in PACKS if p in TIMBRES]
        for pack in packs:
            if pack not in TIMBRES:
                print(f"unknown pack: {pack} (choose from {', '.join(TIMBRES)})", file=sys.stderr)
                return 2
            print(make_pack(pack))
        return 0
    if event not in EVENTS:
        print(f"usage: lennox-sound-fx {' | '.join(EVENTS)} | list", file=sys.stderr)
        return 2
    play(event)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
