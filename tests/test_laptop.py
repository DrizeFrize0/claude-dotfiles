"""Charge limit and keyboard light. Run: python3 tests/test_laptop.py"""
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_STATE_HOME=os.path.join(T, "state"), XDG_CONFIG_HOME=os.path.join(T, "cfg"),
                  XDG_RUNTIME_DIR=os.path.join(T, "run"), LENNOX_LAPTOP_SUDO="")
os.makedirs(os.path.join(T, "bin"))
BLOG = os.path.join(T, "brightnessctl.log")
with open(os.path.join(T, "bin", "brightnessctl"), "w") as f:
    f.write('#!/bin/sh\necho "$*" >> %s\n' % BLOG)
os.chmod(os.path.join(T, "bin", "brightnessctl"), 0o755)
os.environ["PATH"] = os.path.join(T, "bin") + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import laptop as L  # noqa: E402
from lennox import settings as S  # noqa: E402

fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    c or fails.append(what)


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


power, etc, leds = (os.path.join(T, d) for d in ("power", "etc", "leds"))
os.makedirs(power)
check(L.status(power) is None, "no battery -> None")
w(os.path.join(power, "AC", "type"), "Mains\n")
w(os.path.join(power, "hidmouse", "type"), "Battery\n")
w(os.path.join(power, "hidmouse", "scope"), "Device\n")
w(os.path.join(power, "BAT1", "type"), "Battery\n")
w(os.path.join(power, "BAT1", "capacity"), "78\n")
w(os.path.join(power, "BAT1", "status"), "Charging\n")
info = L.status(power)
check(info["name"] == "BAT1" and info["capacity"] == 78 and not info["hardware"], "the laptop battery is found, not the mouse's")

ok, msg = L.set_limit(40, power, etc)
check(not ok, "limits under 50 are refused")
ok, msg = L.set_limit(80, power, etc)
check(ok and "cannot stop charging" in msg and S.get(S.load(), "laptop.charge_limit") == 80, "no hardware: a reminder, and the setting is saved")

# the reminder
sent = []
note = lambda t, b: sent.append(t)  # noqa: E731
st = L.soft_tick({}, 80, {**info, "capacity": 79}, note)
check(sent == [] and not st["told"], "below the limit: quiet")
st = L.soft_tick(st, 80, {**info, "capacity": 80}, note)
check(sent == ["Battery at 80%"] and st["told"], "at the limit: one reminder")
st = L.soft_tick(st, 80, {**info, "capacity": 85}, note)
check(len(sent) == 1, "not repeated while it stays plugged in")
st = L.soft_tick(st, 80, {**info, "state": "Discharging", "capacity": 84}, note)
check(not st["told"], "unplugged: ready for next time")
check(L.soft_tick({"told": True}, 100, info, note) == {"told": False}, "no limit: nothing")
check(L.soft_tick({}, 80, {**info, "hardware": True, "capacity": 90}, note) == {"told": False} and len(sent) == 1,
      "hardware limit: no reminder needed")

# hardware limit
w(os.path.join(power, "BAT1", "charge_control_end_threshold"), "100\n")
ok, msg = L.set_limit(80, power, etc)
check(ok and open(os.path.join(power, "BAT1", "charge_control_end_threshold")).read().strip() == "80", "the threshold is written")
tmpf = open(os.path.join(etc, "tmpfiles.d", "lennox-charge.conf")).read()
check(tmpf == f"w {os.path.join(power, 'BAT1', 'charge_control_end_threshold')} - - - - 80\n", "and kept across restarts (tmpfiles.d)")
ok, msg = L.set_limit(100, power, etc)
check(ok and not os.path.exists(os.path.join(etc, "tmpfiles.d", "lennox-charge.conf")), "100 removes the limit and the boot rule")

# keyboard light
ok, msg = L.kbd("on", root=leds)
check(not ok and "Fn key" in msg, "no keyboard light: says so")
w(os.path.join(leds, "hp::kbd_backlight", "brightness"), "2\n")
w(os.path.join(leds, "hp::kbd_backlight", "max_brightness"), "3\n")
w(os.path.join(leds, "input3::capslock", "brightness"), "0\n")
check(L.kbd_devices(leds) == ["hp::kbd_backlight"], "only the keyboard light is found")
open(BLOG, "w").close()
L.kbd("idle", root=leds)
check("-d hp::kbd_backlight set 0" in open(BLOG).read() and open(L.SAVED).read() == "2", "idle remembers the level and switches off")
w(os.path.join(leds, "hp::kbd_backlight", "brightness"), "0\n")
L.kbd("idle", root=leds)
check(open(L.SAVED).read() == "2", "idle while already off keeps the remembered level")
L.kbd("back", root=leds)
check(open(BLOG).read().strip().endswith("set 2") and not os.path.exists(L.SAVED), "back restores it")
L.kbd("on", root=leds)
check(open(BLOG).read().strip().endswith("set 3"), "on = full brightness")
ok, msg = L.kbd("color", "ff8800", root=leds)
check(not ok and "one color" in msg, "one-color light refuses color")
w(os.path.join(leds, "hp::kbd_backlight", "multi_intensity"), "0 0 0\n")
ok, msg = L.kbd("color", "#ff8800", root=leds)
check(ok and open(os.path.join(leds, "hp::kbd_backlight", "multi_intensity")).read().strip() == "255 136 0", "color writes R G B")
check(not L.kbd("color", "zzz", root=leds)[0], "a bad color is refused")
print("OK laptop" if not fails else "FAILED laptop: %d" % len(fails))
sys.exit(1 if fails else 0)
