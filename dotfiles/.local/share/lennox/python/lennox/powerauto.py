"""Power mode by itself, and a message whenever the power mode changes.

    python3 -m lennox.powerauto watch      (started at login)
    python3 -m lennox.powerauto status     what the rule says right now

The rule (every number is in Settings > Power & Battery):
    plugged in                 -> Performance
    on battery, 80% or more    -> Balanced
    on battery, below 80%      -> Power saver

It only acts when the situation changes (you plug in, unplug, or the battery crosses 80%), so a power mode you
pick by hand stays until the next change. Game mode, which asks for Performance itself, is left alone.
Whoever changes the power mode, you get a message with the new mode and why.
"""

import fcntl
import glob
import json
import os
import subprocess
import sys
import time

from . import settings as S
from . import sh

MODES = ("performance", "balanced", "power-saver")
LABEL = {"performance": "Performance", "balanced": "Balanced", "power-saver": "Power saver"}
ICON = {"performance": "power-profile-performance-symbolic", "balanced": "power-profile-balanced-symbolic",
        "power-saver": "power-profile-power-saver-symbolic"}
STATE = os.path.join(S.RUNTIME_DIR, "powerauto.json")
LOCK = os.path.join(S.RUNTIME_DIR, "powerauto.lock")
EVERY = 10
HYSTERESIS = 2          # percent: a charger that flickers at 80% must not flip the mode back and forth


def decide(on_ac, capacity, band, cfg):
    """(mode, band, why). band is 'high' or 'low' from the last time (None at first)."""
    if on_ac:
        return cfg["ac_mode"], "ac", "plugged in"
    t = cfg["threshold"]
    high = capacity >= (t + HYSTERESIS if band == "low" else t)
    if high:
        return cfg["battery_high_mode"], "high", f"on battery, {capacity}% (at least {t}%)"
    return cfg["battery_low_mode"], "low", f"on battery, {capacity}% (below {t}%)"


class Brain:
    """The decisions, with no side effects: tick() says what to do, the loop does it. Tests drive this."""

    def __init__(self):
        self.band = None
        self.wanted = None        # the mode the rule last asked for (a change here is a real change in the situation)
        self.set_to = None        # what we last set, to tell our changes from yours
        self.why = ""
        self.seen = None

    def tick(self, cfg, on_ac, capacity, current, game_mode):
        """cfg: the settings 'power' section. Returns [("set", mode), ("notify", mode, why)]."""
        actions = []
        if cfg["auto"] and not game_mode and on_ac is not None:
            mode, band, why = decide(on_ac, capacity, self.band, cfg)
            self.band = band
            if mode != self.wanted and current != mode:
                actions.append(("set", mode))
                self.set_to, self.why = mode, why
            self.wanted = mode
        if cfg["notify_changes"] and current and current != self.seen and self.seen is not None:
            ours = current == self.set_to and self.why
            actions.append(("notify", current, self.why if ours else "changed by you or another program"))
            if ours:
                self.set_to = None          # the next change to this same mode is not ours
        if current:
            self.seen = current
        return actions


def power_state():
    """(on AC?, battery %) or (None, None) on a desktop."""
    battery = None
    for supply in sorted(glob.glob("/sys/class/power_supply/*")):
        if sh.read_text(os.path.join(supply, "type")) == "Battery" and sh.read_text(os.path.join(supply, "scope")) != "Device":
            battery = supply
            break
    if battery is None:
        return None, None
    capacity = sh.read_text(os.path.join(battery, "capacity"))
    for supply in glob.glob("/sys/class/power_supply/*"):
        if sh.read_text(os.path.join(supply, "type")) == "Mains":
            return sh.read_text(os.path.join(supply, "online")) == "1", int(capacity) if capacity.isdigit() else 100
    return sh.read_text(os.path.join(battery, "status")) != "Discharging", int(capacity) if capacity.isdigit() else 100


def active_profile():
    """The power mode right now: performance, balanced or power-saver (D-Bus when busctl exists: much lighter than Python)."""
    out = sh.out(["busctl", "--system", "get-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles",
                  "net.hadess.PowerProfiles", "ActiveProfile"], 3)
    if out.startswith('s "'):
        return out.split('"')[1]
    return sh.out(["powerprofilesctl", "get"], 3) or None


def _write_state(mode, why):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"mode": mode, "why": why, "time": time.time()}, f)


def announce(mode, why):
    """The message: a notification that replaces the last one, and the island."""
    text = f"Power mode: {LABEL.get(mode, mode)}"
    subprocess.run(["notify-send", "-a", "Lennox", "-i", ICON.get(mode, "battery"), "-t", "4000",
                    "-h", "string:x-canonical-private-synchronous:lennox-power", text, why[:1].upper() + why[1:]],
                   capture_output=True, check=False)
    sh.island(ICON.get(mode, "battery"), f"{LABEL.get(mode, mode)} · {why}", 4)
    _write_state(mode, why)
    subprocess.run(["pkill", "-RTMIN+15", "-x", "waybar"], capture_output=True, check=False)       # the bar's power item


def game_mode_on():
    return sh.out([sh.bin_path("lennox-mode"), "game", "status"]) == "on"


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")  # noqa: SIM115  held for the life of the process
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    brain = Brain()
    while True:
        try:
            cfg = S.load()["power"]
            on_ac, capacity = power_state()
            current = active_profile()
            if cfg["auto"] or cfg["notify_changes"]:
                for action in brain.tick(cfg, on_ac, capacity, current, game_mode_on()):
                    if action[0] == "set":
                        sh.run(["powerprofilesctl", "set", action[1]], 5)
                    else:
                        announce(action[1], action[2])
        except Exception:  # noqa: BLE001  never stop watching because of one odd reading
            pass
        time.sleep(EVERY)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    if mode == "watch":
        return watch()
    if mode == "status":
        cfg = S.load()["power"]
        on_ac, capacity = power_state()
        if on_ac is None:
            print("No battery: this is a desktop, the rule doesn't apply.")
            return 0
        want, _band, why = decide(on_ac, capacity, None, cfg)
        print(f"Now: {LABEL.get(active_profile(), active_profile())}  ·  the rule says: {LABEL[want]} ({why})"
              f"  ·  automatic: {'on' if cfg['auto'] else 'off'}")
        return 0
    print("usage: lennox-powerauto watch | status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
