"""Fan and noise profiles: Silent keeps the fans quiet at night, Turbo is for games.

    python3 -m lennox.fan status        JSON: profile, temperature, fan speeds
    python3 -m lennox.fan apply         set the processor and power mode to the chosen profile
    python3 -m lennox.fan set silent|cool|normal|turbo

Cool = the processor held to 80%, which trims the short heat spikes (98 degrees for a second) and costs almost nothing you can feel.
Silent = power-saver mode and the processor capped to 60% with turbo off, which
keeps most laptops' fans down to a whisper. Turbo = performance mode. Fan
*speeds* are shown where the laptop reports them; most can't be set directly.
"""

import glob
import json
import os
import sys

from . import care
from . import settings as S
from . import sh

PERF = {"silent": "quiet", "cool": "balanced", "normal": "balanced", "turbo": "max"}
HELPER = "/usr/local/bin/lennox-cpucap"
PSTATE = "/sys/devices/system/cpu/intel_pstate"


def fan_speeds(root="/sys/class/hwmon"):
    out = []
    for f in sorted(glob.glob(os.path.join(root, "hwmon*", "fan*_input"))):
        raw = sh.read_text(f)
        if raw.isdigit():
            out.append(int(raw))
    return out


def status(settings=None):
    settings = settings or S.load()
    cap = sh.read_text(os.path.join(PSTATE, "max_perf_pct"))
    return {"profile": settings["fan"]["profile"], "temp": care.cpu_temp(), "fans": fan_speeds(),
            "cap": int(cap) if cap.isdigit() else None, "power_mode": sh.out([sh.bin_path("lennox-perf"), "status"]),
            "can_cap": os.path.isdir(PSTATE) and os.path.exists(HELPER), "fan_control": bool(fan_control())}


def fan_control(root="/sys/class/hwmon"):
    """The hwmon folders where this laptop lets software set the fan (the HP driver's pwm1_enable)."""
    found = []
    for d in sorted(glob.glob(os.path.join(root, "hwmon*"))):
        if sh.read_text(os.path.join(d, "name")) in ("hp", "hp_wmi", "hp-wmi") and os.path.exists(os.path.join(d, "pwm1_enable")):
            found.append(d)
    return found


def probe(root="/sys/class/hwmon", platform="/sys/firmware/acpi"):
    """What this laptop offers for fan control, as lines of text (for lennox-fan probe)."""
    lines = []
    profile = sh.read_text(os.path.join(platform, "platform_profile"))
    choices = sh.read_text(os.path.join(platform, "platform_profile_choices"))
    lines.append(f"Firmware profile (the HP fan curve): {profile or 'not offered'}" + (f"  (choices: {choices})" if choices else ""))
    names = [f"{os.path.basename(d)}={sh.read_text(os.path.join(d, 'name'))}" for d in sorted(glob.glob(os.path.join(root, "hwmon*")))]
    lines.append("Sensors: " + (", ".join(names) or "none"))
    speeds = fan_speeds(root)
    lines.append("Fan speeds: " + (", ".join(f"{s} rpm" for s in speeds) if speeds else "not reported"))
    ctl = fan_control(root)
    lines.append("Fan control from Linux: " + ("yes (" + ", ".join(os.path.basename(d) for d in ctl) + ")" if ctl else "no"))
    if not ctl:
        lines.append("  This kernel's HP driver doesn't expose the fan on this model. The fan curve then follows the firmware "
                     "profile above, which Quiet/Balanced/Max (SUPER + ALT + P) switch. Send this output so I can add the model.")
    return lines


def apply(profile):
    sh.run([sh.bin_path("lennox-perf"), PERF[profile]])
    if os.path.exists(HELPER):
        sh.run(["pkexec", HELPER, profile], 15)
        if fan_control():
            sh.run(["pkexec", HELPER, "fan-max" if profile == "turbo" else "fan-auto"], 15)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    if mode == "status":
        print(json.dumps(status()))
    elif mode == "probe":
        print("\n".join(probe()))
    elif mode == "boost" and len(argv) > 2 and argv[2] in ("on", "off"):
        sh.run(["pkexec", HELPER, "fan-max" if argv[2] == "on" else "fan-auto"], 15)
    elif mode == "apply":
        apply(S.load()["fan"]["profile"])
    elif mode == "set" and len(argv) > 2 and argv[2] in PERF:
        S.set_value("fan.profile", argv[2])
        apply(argv[2])
    else:
        print("usage: lennox-fan status | probe | boost on|off | apply | set silent|cool|normal|turbo", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
