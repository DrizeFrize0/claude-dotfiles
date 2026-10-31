"""System monitor for the bar: temperatures, load, fans and what's busy.

    python3 -m lennox.sysmon waybar|text

The bar item shows the CPU temperature (and the NVIDIA GPU's, but only
while it is already awake: asking a sleeping GPU wakes it and costs
battery). The tooltip has the details; clicking opens Mission Center.
"""

import glob
import json
import os
import subprocess
import sys
import time

from .widgets import data

WARM = 75   # °C: the bar item turns orange
HOT = 88    # °C: red, and the laptop is close to slowing itself down

SYS = os.environ.get("LENNOX_SYS", "/sys")
PROC = os.environ.get("LENNOX_PROC", "/proc")


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def nvidia_device():
    for dev in sorted(glob.glob(os.path.join(SYS, "bus/pci/devices/*"))):
        if _read(os.path.join(dev, "vendor")) == "0x10de" and \
                (_read(os.path.join(dev, "class"), "") or "").startswith(("0x0300", "0x0302")):
            return dev
    return None


def gpu():
    """{'awake': bool, 'temp', 'load', 'watts'} for the NVIDIA GPU, or None without one."""
    dev = nvidia_device()
    if not dev:
        return None
    if _read(os.path.join(dev, "power/runtime_status")) == "suspended":
        return {"awake": False}
    info = {"awake": True}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        temp, load, watts = (x.strip() for x in out.stdout.splitlines()[0].split(","))
        info.update(temp=float(temp), load=float(load))
        try:
            info["watts"] = float(watts)
        except ValueError:
            pass
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return info


def fans():
    """Fan speeds in RPM (only fans that report one)."""
    speeds = []
    for path in sorted(glob.glob(os.path.join(SYS, "class/hwmon/hwmon*/fan*_input"))):
        try:
            rpm = int(_read(path, "0"))
        except ValueError:
            continue
        if rpm > 0:
            speeds.append(rpm)
    return speeds


def battery_watts():
    """Power the laptop draws from its battery right now, or None on the charger."""
    for bat in sorted(glob.glob(os.path.join(SYS, "class/power_supply/BAT*"))):
        if _read(os.path.join(bat, "status")) != "Discharging":
            continue
        try:
            power = _read(os.path.join(bat, "power_now"))
            if power is not None:
                return int(power) / 1e6
            # Some batteries report current and voltage instead
            current = int(_read(os.path.join(bat, "current_now")))
            voltage = int(_read(os.path.join(bat, "voltage_now")))
            return current * voltage / 1e12
        except (TypeError, ValueError):
            continue
    return None


def _proc_times():
    """{pid: (name, cpu ticks)} for every process."""
    times = {}
    for stat in glob.glob(os.path.join(PROC, "[0-9]*/stat")):
        raw = _read(stat)
        if not raw:
            continue
        # comm is in parentheses and may contain spaces
        start, end = raw.find("("), raw.rfind(")")
        if start < 0 or end < 0:
            continue
        fields = raw[end + 2:].split()
        try:
            times[stat] = (raw[start + 1:end], int(fields[11]) + int(fields[12]))
        except (IndexError, ValueError):
            continue
    return times


def sample(seconds=0.5):
    """Measure CPU use and the busiest apps over a short moment."""
    meter = data.CpuMeter(os.path.join(PROC, "stat"))
    meter.percent()
    before = _proc_times()
    time.sleep(seconds)
    cpu = meter.percent()
    after = _proc_times()
    ticks = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    busy = {}
    for key, (name, t1) in after.items():
        if key in before and before[key][0] == name:
            busy[name] = busy.get(name, 0.0) + (t1 - before[key][1]) / ticks / seconds * 100
    top = sorted(((v, k) for k, v in busy.items() if v >= 1), reverse=True)[:3]
    return cpu, [(name, value) for value, name in top]


def collect(seconds=0.5):
    cpu, top = sample(seconds)
    return {
        "cpu": cpu,
        "cpu_temp": data.temperature(os.path.join(SYS, "class/hwmon"), os.path.join(SYS, "class/thermal")),
        "gpu": gpu(),
        "fans": fans(),
        "memory": data.memory(os.path.join(PROC, "meminfo")),
        "battery_watts": battery_watts(),
        "top": top,
    }


def level(info):
    temps = [t for t in (info.get("cpu_temp"), (info.get("gpu") or {}).get("temp")) if t is not None]
    hottest = max(temps) if temps else 0
    if hottest >= HOT:
        return "hot"
    if hottest >= WARM:
        return "warm"
    return "cool"


def waybar(info):
    parts = []
    if info.get("cpu_temp") is not None:
        parts.append(f"󰔏 {info['cpu_temp']:.0f}°")
    elif info.get("cpu") is not None:
        parts.append(f"󰻠 {info['cpu']:.0f}%")
    g = info.get("gpu") or {}
    if g.get("awake") and g.get("temp") is not None:
        parts.append(f"󰢮 {g['temp']:.0f}°")

    tip = []
    if info.get("cpu") is not None:
        line = f"CPU  {info['cpu']:.0f}%"
        if info.get("cpu_temp") is not None:
            line += f"  ·  {info['cpu_temp']:.0f}°C"
        tip.append(line)
    if info.get("gpu") is not None:
        if not g.get("awake"):
            tip.append("NVIDIA GPU  asleep (saving battery)")
        else:
            line = "NVIDIA GPU"
            if g.get("load") is not None:
                line += f"  {g['load']:.0f}%"
            if g.get("temp") is not None:
                line += f"  ·  {g['temp']:.0f}°C"
            if g.get("watts") is not None:
                line += f"  ·  {g['watts']:.0f} W"
            tip.append(line)
    if info.get("memory"):
        percent, used, total = info["memory"]
        tip.append(f"Memory  {used:.1f} of {total:.0f} GB  ({percent:.0f}%)")
    if info.get("fans"):
        tip.append("Fans  " + ", ".join(f"{rpm} rpm" for rpm in info["fans"]))
    if info.get("battery_watts") is not None:
        tip.append(f"Battery use  {info['battery_watts']:.1f} W")
    if info.get("top"):
        tip.append("")
        tip.append("Busiest right now:")
        tip += [f"  {name}  {value:.0f}%" for name, value in info["top"]]
    state = level(info)
    if state == "hot":
        tip.append("")
        tip.append("Very hot: the laptop will slow itself down. Check the vents aren't covered.")
    tip.append("")
    tip.append("Click for the full monitor (SUPER + CTRL + ESC)")
    return {"text": "  ".join(parts), "tooltip": "\n".join(tip), "class": state,
            "percentage": round(info.get("cpu") or 0)}


def main(argv):
    mode = argv[1] if len(argv) > 1 else "text"
    info = collect()
    if mode == "waybar":
        print(json.dumps(waybar(info), ensure_ascii=False))
    elif mode == "json":
        print(json.dumps(info, ensure_ascii=False))
    else:
        print(waybar(info)["tooltip"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
