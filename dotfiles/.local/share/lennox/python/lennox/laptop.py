"""Laptop tuning: spare the battery with a charge limit, and tame the keyboard light.

    python3 -m lennox.laptop status               battery, charge limit, keyboard light
    python3 -m lennox.laptop limit 80|100         stop charging at 80% (100 = no limit)
    python3 -m lennox.laptop tick                 (the battery watcher calls it) reminds you to unplug at the limit
    python3 -m lennox.laptop kbd on|off|idle|back|color RRGGBB|status

A battery that sits at 100% on the charger wears out faster; 80% roughly doubles its life. Some laptops can
stop charging by themselves (the kernel offers charge_control_end_threshold): then the limit is set in the
hardware and kept across restarts. Many HP laptops cannot: then Lennox tells you to unplug at the limit.
The keyboard light turns itself off when you stop typing (Settings > Power) and back on when you return.
"""

import os
import sys

from . import settings as S
from . import sh

POWER = "/sys/class/power_supply"
LEDS = "/sys/class/leds"
ETC = "/etc"
SUDO = os.environ.get("LENNOX_LAPTOP_SUDO", "sudo").split()
SOFT = os.path.join(S.RUNTIME_DIR, "charge-told")
SAVED = os.path.join(S.RUNTIME_DIR, "kbd-saved")


def read(path, default=""):
    return sh.read_text(path, default)


def battery_dir(root=POWER):
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None
    for n in names:
        d = os.path.join(root, n)
        if read(os.path.join(d, "type")) == "Battery" and read(os.path.join(d, "scope")) != "Device":
            return d
    return None


def status(root=POWER):
    d = battery_dir(root)
    if not d:
        return None
    threshold = os.path.join(d, "charge_control_end_threshold")
    try:
        capacity = int(read(os.path.join(d, "capacity"), "0"))
    except ValueError:
        capacity = 0
    return {"dir": d, "name": os.path.basename(d), "capacity": capacity, "state": read(os.path.join(d, "status")),
            "hardware": os.path.exists(threshold), "threshold": read(threshold) if os.path.exists(threshold) else ""}


def set_limit(value, root=POWER, etc=ETC, settings_write=True):
    """Returns (ok, message)."""
    if not 50 <= value <= 100:
        return False, "The limit is between 50 and 100."
    info = status(root)
    if not info:
        return False, "No battery found (this is a desktop?)."
    if settings_write:
        S.set_value("laptop.charge_limit", value)
    tmp = os.path.join(etc, "tmpfiles.d", "lennox-charge.conf")
    if info["hardware"]:
        path = os.path.join(info["dir"], "charge_control_end_threshold")
        code, _out, err = sh.run(SUDO + ["tee", path], 10, data=f"{value}\n")
        if code != 0:
            return False, f"The battery refused {value}% ({err.strip() or 'no permission'}). A reminder to unplug is used instead."
        if value < 100:
            sh.run(SUDO + ["mkdir", "-p", os.path.dirname(tmp)], 10)
            sh.run(SUDO + ["tee", tmp], 10, data=f"w {path} - - - - {value}\n")
        else:
            sh.run(SUDO + ["rm", "-f", tmp], 10)
        return True, (f"The battery stops charging at {value}% (kept across restarts)." if value < 100
                      else "No charge limit: the battery charges fully.")
    if value < 100:
        return True, (f"This laptop cannot stop charging by itself. Lennox will tell you to unplug at {value}%.")
    return True, "No charge limit."


def soft_tick(state, limit, info, notify):
    """The reminder for laptops without a hardware limit. state: {'told': bool}. Returns the new state."""
    if not info or info["hardware"] or limit >= 100:
        return {"told": False}
    charging = info["state"] in ("Charging", "Full", "Not charging")
    if not charging:
        return {"told": False}
    if info["capacity"] >= limit and not state.get("told"):
        notify("Battery at %d%%" % info["capacity"], f"Unplug now to spare the battery (limit {limit}%).")
        return {"told": True}
    if info["capacity"] < limit - 5:
        return {"told": False}
    return {"told": bool(state.get("told"))}


# ------------------------------------------------------------------ keyboard light

def kbd_devices(root=LEDS):
    try:
        return sorted(n for n in os.listdir(root) if "kbd_backlight" in n)
    except OSError:
        return []


def kbd(action, arg="", root=LEDS, run=sh.run):
    """Returns (ok, message)."""
    devices = kbd_devices(root)
    if not devices:
        return False, "No keyboard light that Linux can control on this laptop (use the Fn key)."
    name = devices[0]
    path = os.path.join(root, name)
    try:
        top = int(read(os.path.join(path, "max_brightness"), "1"))
    except ValueError:
        top = 1
    brightnessctl = ["brightnessctl", "-q", "-d", name]
    if action == "status":
        return True, f"{name}: {read(os.path.join(path, 'brightness'), '?')} of {top}" + \
            (" (colors: yes)" if os.path.exists(os.path.join(path, "multi_intensity")) else "")
    if action == "off":
        run(brightnessctl + ["set", "0"], 5)
        return True, "Keyboard light off."
    if action == "on":
        run(brightnessctl + ["set", str(top)], 5)
        return True, "Keyboard light on."
    if action == "idle":                       # you stopped typing: remember the level, switch off
        level = read(os.path.join(path, "brightness"), "0")
        if level not in ("", "0"):
            os.makedirs(os.path.dirname(SAVED), exist_ok=True)
            with open(SAVED, "w", encoding="utf-8") as f:
                f.write(level)
            run(brightnessctl + ["set", "0"], 5)
        return True, "idle"
    if action == "back":
        level = read(SAVED)
        if level:
            run(brightnessctl + ["set", level], 5)
            try:
                os.remove(SAVED)
            except OSError:
                pass
        return True, "back"
    if action == "color":
        hex_color = arg.lstrip("#")
        if len(hex_color) != 6 or any(c not in "0123456789abcdefABCDEF" for c in hex_color):
            return False, "A color like ff8800."
        target = os.path.join(path, "multi_intensity")
        if not os.path.exists(target):
            return False, "This keyboard light has one color only."
        rgb = " ".join(str(int(hex_color[i:i + 2], 16)) for i in (0, 2, 4))
        code, _out, err = run(SUDO + ["tee", target], 5, data=rgb + "\n")
        return (code == 0), ("Color set." if code == 0 else f"Could not set it ({err.strip() or 'no permission'}).")
    return False, "usage: lennox-laptop kbd on|off|idle|back|color RRGGBB|status"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        info = status()
        if not info:
            print("No battery found.")
        else:
            limit = S.get(S.load(), "laptop.charge_limit")
            print(f"Battery {info['capacity']}% ({info['state'] or '?'})")
            print(f"Charge limit: {limit}%" + (f" (hardware: stops at {info['threshold']}%)" if info["hardware"]
                  else " (this laptop has no hardware limit: Lennox reminds you to unplug)" if limit < 100 else ""))
        print("Keyboard light: " + kbd("status")[1])
        return 0
    if cmd == "limit" and len(argv) > 2 and argv[2].isdigit():
        ok, msg = set_limit(int(argv[2]))
        print(msg)
        return 0 if ok else 1
    if cmd == "tick":
        limit = S.get(S.load(), "laptop.charge_limit")
        info = status()
        try:
            with open(SOFT, encoding="utf-8") as f:
                state = {"told": f.read().strip() == "1"}
        except OSError:
            state = {"told": False}
        state = soft_tick(state, limit, info, lambda t, b: sh.notify(t, b, "battery-full-charged"))
        os.makedirs(os.path.dirname(SOFT), exist_ok=True)
        with open(SOFT, "w", encoding="utf-8") as f:
            f.write("1" if state["told"] else "0")
        return 0
    if cmd == "kbd":
        ok, msg = kbd(argv[2] if len(argv) > 2 else "status", argv[3] if len(argv) > 3 else "")
        if msg not in ("idle", "back"):
            print(msg)
        return 0 if ok else 1
    print("usage: lennox-laptop status | limit 80 | tick | kbd on|off|color RRGGBB", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
