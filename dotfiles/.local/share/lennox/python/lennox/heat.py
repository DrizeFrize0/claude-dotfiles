"""Why is the laptop hot? Looks at the temperature, what is using the processor, the power settings and Lennox's own extras.

    python3 -m lennox.heat [check]     what it sees and what to do
    python3 -m lennox.heat cool        the safe steps now: Quiet power mode, game mode off, extras off
    python3 -m lennox.heat watch [S]   record the temperature and the busiest program every second for S seconds (60),
                                       then say what causes the spikes

Nothing here is permanent: Settings turns everything back on.
"""

import glob
import os
import subprocess
import sys
import time

from . import care
from . import fan
from . import settings as S
from . import sh

EXTRAS = ("pet", "visualizer", "cursorfx")


def read_int(path):
    raw = sh.read_text(path)
    return int(raw) if raw.lstrip("-").isdigit() else None


def top_processes(n=6):
    out = sh.out(["ps", "-eo", "pcpu,comm,args", "--sort=-pcpu", "--no-headers"], 5)
    rows = []
    for line in out.splitlines()[: n + 4]:
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[1] != "ps":
            try:
                args = parts[2] if len(parts) > 2 else ""
                label = parts[1]
                if "-m lennox." in args:                         # which Lennox part is it?
                    label = "lennox " + args.split("-m lennox.", 1)[1].split()[0]
                rows.append((float(parts[0]), label, args[:60]))
            except ValueError:
                pass
    return rows[:n]


def cpu_freq_mhz():
    freqs = [read_int(f) for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")]
    freqs = [f for f in freqs if f]
    return sum(freqs) / len(freqs) / 1000 if freqs else None


def throttle_count():
    total = 0
    for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/thermal_throttle/*_throttle_count"):
        total += read_int(f) or 0
    return total


def running_extras():
    on = []
    for name in EXTRAS:
        try:
            with open(os.path.join(S.RUNTIME_DIR, f"{name}.pid"), encoding="utf-8") as f:
                os.kill(int(f.read()), 0)
            on.append(name)
        except (OSError, ValueError):
            pass
    return on


def snapshot():
    load = os.getloadavg()[0] / max(os.cpu_count() or 1, 1) * 100
    return {"temp": care.cpu_temp(), "load": load, "procs": top_processes(), "freq": cpu_freq_mhz(),
            "power_mode": sh.out([sh.bin_path("lennox-perf"), "status"]),
            "game_mode": sh.out([sh.bin_path("lennox-mode"), "game", "status"]) == "on",
            "turbo_off": read_int("/sys/devices/system/cpu/intel_pstate/no_turbo") == 1,
            "cap": read_int("/sys/devices/system/cpu/intel_pstate/max_perf_pct"),
            "epp": sh.read_text("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"),
            "fans": fan.fan_speeds(), "gpu_awake": care.nvidia_awake(), "throttled": throttle_count(),
            "persistenced": sh.run(["systemctl", "is-active", "--quiet", "nvidia-persistenced"])[0] == 0,
            "thermald": None if not os.path.exists("/usr/bin/thermald") and not os.path.exists("/usr/sbin/thermald")
                        else sh.run(["systemctl", "is-active", "--quiet", "thermald"])[0] == 0,
            "extras": running_extras(), "livewall": sh.out([sh.bin_path("lennox-livewall"), "status"]).startswith("playing")}


def diagnose(s):
    """[(what is wrong, what to do)] from a snapshot. Pure: the tests feed it made-up snapshots."""
    out = []
    hot = s["temp"] is not None and s["temp"] >= 85
    busiest = s["procs"][0] if s["procs"] else None
    if busiest and busiest[0] >= 40:
        out.append((f"{busiest[1]} is using {busiest[0]:.0f}% of a processor core ({busiest[2]})",
                    f"Close it, or kill it: pkill {busiest[1].split('/')[0]}"))
    if s["game_mode"]:
        out.append(("Game mode is on (performance power mode, no limits)", "lennox-mode game off, or let it turn off when the game closes"))
    if s["power_mode"] == "max":
        out.append(("The power mode is Max performance", "lennox-perf quiet (or balanced)"))
    if s["epp"] == "performance" and not s["game_mode"]:
        out.append(("The processor is told to favor performance (energy preference: performance)", "lennox-perf balanced"))
    if s["freq"] and s["freq"] > 3000 and s["load"] < 25 and not s["turbo_off"]:
        out.append((f"The processor runs at {s['freq'] / 1000:.1f} GHz while almost nothing is happening", "lennox-fan set cool (trims the spikes), or silent (turbo off)"))
    if s["extras"]:
        out.append((f"Lennox extras are running: {', '.join(s['extras'])}", "Settings > Extras, or: lennox-heat cool"))
    if s["livewall"]:
        out.append(("A live (video) wallpaper is playing", "lennox-livewall stop (or turn on pausing on battery in Settings > Wallpaper)"))
    if s["gpu_awake"]:
        out.append(("The NVIDIA graphics chip is awake (it adds heat and drains the battery)", "Settings > Graphics: integrated mode, and close what uses it: nvidia-smi"))
    if s.get("persistenced"):
        out.append(("nvidia-persistenced keeps the NVIDIA chip awake all day (hot and drains the battery)", "Run: lennox upgrade (it turns it off), or: sudo systemctl disable --now nvidia-persistenced"))
    if s.get("thermald") is None and s["temp"] is not None and s["temp"] >= 80:
        out.append(("thermald (Intel's heat manager) isn't installed", "Run: lennox upgrade, or: sudo pacman -S thermald && sudo systemctl enable --now thermald"))
    elif s.get("thermald") is False:
        out.append(("thermald is installed but not running", "sudo systemctl enable --now thermald"))
    if s["throttled"]:
        out.append((f"The processor has slowed itself down because of heat {s['throttled']} times", "Clean the fans and vents, see below"))
    if not s["fans"]:
        out.append(("This laptop doesn't report its fan speed to Linux", "Check by ear and hand: warm air should blow out of the vents. If it doesn't, the fan is the problem"))
    elif max(s["fans"]) == 0 and hot:
        out.append(("A fan reports 0 rpm while the processor is hot", "The fan isn't spinning: a hardware or BIOS problem, see below"))
    if hot and s["load"] < 20 and not [d for d in out if "using" in d[0] or "Game" in d[0] or "extras" in d[0]]:
        out.append(("Hot even though almost nothing is using the processor", "That points at the hardware: dust, dried thermal paste, a blocked vent or a fan problem, see below"))
    return out


HARDWARE = """If it stays hot after the steps above, it is probably hardware (very common on gaming laptops after a year or two):
  - Blow compressed air through the vents (laptop off), or open the back and clean the fans
  - Don't use it on a bed or couch: the vents are underneath and get blocked. A cooling stand helps a lot
  - Dried thermal paste: re-pasting the processor often drops 15-25 degrees
  - HP Victus laptops: check the BIOS (F10) for a fan setting (fan always on, or performance mode) and update the BIOS
  - Above 95 degrees for long can shorten the laptop's life: Quiet mode below is the safe choice until it is fixed"""


def report(s):
    lines = [f"Processor: {s['temp']:.0f}°C" if s["temp"] is not None else "Processor: temperature not reported",
             f"Load: about {s['load']:.0f}% of all cores  ·  speed: {s['freq'] / 1000:.1f} GHz" if s["freq"] else f"Load: about {s['load']:.0f}%",
             f"Power mode: {s['power_mode'] or 'unknown'}  ·  turbo: {'off' if s['turbo_off'] else 'on'}  ·  limit: {s['cap'] if s['cap'] is not None else '?'}%",
             "Fans: " + (", ".join(f"{f} rpm" for f in s["fans"]) if s["fans"] else "not reported"),
             "", "Using the processor most:"]
    lines += [f"  {p[0]:5.1f}%  {p[1]}" for p in s["procs"]] or ["  (nothing)"]
    lines += ["", "What I found:"]
    found = diagnose(s)
    lines += [f"  - {what}\n      -> {todo}" for what, todo in found] or ["  - Nothing in the software explains it"]
    if s["temp"] is not None and s["temp"] >= 85:
        lines += ["", HARDWARE, "", "Right now: lennox-heat cool"]
    return "\n".join(lines)


def cool():
    """The safe steps now. Reversible: power mode and extras come back from Settings."""
    steps = []
    if sh.out([sh.bin_path("lennox-perf"), "status"]) != "quiet":
        sh.run([sh.bin_path("lennox-perf"), "quiet"])
        steps.append("Power mode: Quiet")
    if sh.out([sh.bin_path("lennox-mode"), "game", "status"]) == "on":
        sh.run([sh.bin_path("lennox-mode"), "game", "off"])
        steps.append("Game mode: off")
    for name in running_extras():
        sh.run([sh.bin_path(f"lennox-{name}"), "stop"])
        steps.append(f"Stopped: {name}")
    if subprocess.run(["pkill", "-f", "python3 -m lennox.screensaver"], capture_output=True, check=False).returncode == 0:
        steps.append("Stopped: a screensaver that was still running")
    if os.path.exists(fan.HELPER):
        sh.run(["pkexec", fan.HELPER, "silent"], 15)
        steps.append("Processor held to 60% with turbo off (until you pick Normal in Settings > Extras > Fan and noise)")
    return steps


def summarize(samples, hot=85):
    """samples: [(temp, program, cpu%)] one per second. Returns the lines of the answer."""
    temps = [t for t, _p, _c in samples if t is not None]
    if not temps:
        return ["The laptop doesn't report its temperature, so there is nothing to record."]
    peak, low = max(temps), min(temps)
    over = [(t, p, c) for t, p, c in samples if t is not None and t >= hot]
    lines = [f"Temperature over {len(samples)} seconds: lowest {low:.0f}°C, highest {peak:.0f}°C, over {hot}°C for {len(over)} seconds"]
    if not over:
        return lines + ["No real spike while recording. Do what usually makes it spike (open the browser, a game) while this runs."]
    culprits = {}
    for _t, program, cpu in over:
        culprits[program] = culprits.get(program, 0) + cpu
    ranked = sorted(culprits.items(), key=lambda kv: -kv[1])
    lines.append("What was using the processor most while it was hot:")
    lines += [f"  - {program}" for program, _c in ranked[:3]]
    if len(over) <= 12 and low < 70:
        lines += ["", "These are SHORT spikes: the processor races for a few seconds (turbo boost) when something starts, then calms down.",
                  "That is normal and harmless. To trim them: lennox-fan set cool (holds the processor to 80%, you will barely feel it)."]
    else:
        lines += ["", "The heat lasts: something keeps the processor busy. Close the program above, then run lennox-heat cool."]
    return lines


def watch(seconds):
    samples = []
    print(f"Recording for {seconds} seconds: use the laptop the way it usually spikes (open the browser, start Spotify, a game)...")
    for i in range(seconds):
        top = top_processes(1)
        samples.append((care.cpu_temp(), top[0][1] if top else "?", top[0][0] if top else 0.0))
        if i % 10 == 9:
            print(f"  {i + 1}s: {samples[-1][0]:.0f}°C, busiest: {samples[-1][1]}" if samples[-1][0] is not None else f"  {i + 1}s")
        time.sleep(1)
    print()
    print("\n".join(summarize(samples)))


def main(argv):
    mode = argv[1] if len(argv) > 1 else "check"
    if mode == "check":
        print(report(snapshot()))
    elif mode == "watch":
        watch(int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 60)
    elif mode == "cool":
        before = care.cpu_temp()
        steps = cool()
        print("\n".join(f"  - {x}" for x in steps) or "  - Nothing to change: it is already as cool as the software can make it")
        print("\nWaiting 20 seconds to see the effect...")
        time.sleep(20)
        after = care.cpu_temp()
        if before is not None and after is not None:
            print(f"Processor: {before:.0f}°C -> {after:.0f}°C (it keeps dropping for a minute or two)")
    else:
        print("usage: lennox-heat [check | cool | watch [SECONDS]]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
