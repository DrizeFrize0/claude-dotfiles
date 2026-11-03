"""Fan and noise profiles: Silent keeps the fans quiet at night, Turbo is for games.

    python3 -m lennox.fan status        JSON: profile, temperature, fan speeds
    python3 -m lennox.fan apply         set the processor and power mode to the chosen profile
    python3 -m lennox.fan set silent|normal|turbo

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

PERF = {"silent": "quiet", "normal": "balanced", "turbo": "max"}
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
            "can_cap": os.path.isdir(PSTATE) and os.path.exists(HELPER)}


def apply(profile):
    sh.run([sh.bin_path("lennox-perf"), PERF[profile]])
    if os.path.exists(HELPER):
        sh.run(["pkexec", HELPER, profile], 15)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    if mode == "status":
        print(json.dumps(status()))
    elif mode == "apply":
        apply(S.load()["fan"]["profile"])
    elif mode == "set" and len(argv) > 2 and argv[2] in PERF:
        S.set_value("fan.profile", argv[2])
        apply(argv[2])
    else:
        print("usage: lennox-fan status | apply | set silent|normal|turbo", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
