"""Battery doctor: what uses the battery while you are unplugged.

    python3 -m lennox.batterydoc report [--json]
    python3 -m lennox.batterydoc sample          (Lennox's watcher does this once a minute while unplugged)

It is an estimate: every minute on battery it notes the power the battery is giving and which programs were busy, then
shares the power above the laptop's quiet baseline between the programs by how much processor each used. It is good for
spotting the one program that eats the battery, not for exact numbers.
"""

import glob
import json
import os
import sys
import time

from . import settings as S
from . import sh

LOG = os.path.join(S.STATE_DIR, "batterydoc.jsonl")
KEEP_DAYS = 3
IDLE_LOAD = 15.0          # total processor % under which the laptop counts as idle (the baseline power)


def battery_dir():
    for supply in sorted(glob.glob("/sys/class/power_supply/*")):
        if sh.read_text(os.path.join(supply, "type")) == "Battery" and sh.read_text(os.path.join(supply, "scope")) != "Device":
            return supply
    return None


def _num(path):
    raw = sh.read_text(path)
    return int(raw) if raw.lstrip("-").isdigit() else None


def power_watts(base):
    """Watts the battery is giving now (None if the laptop doesn't say)."""
    p = _num(os.path.join(base, "power_now"))
    if p is None:
        i, v = _num(os.path.join(base, "current_now")), _num(os.path.join(base, "voltage_now"))
        p = i * v / 1e6 if i is not None and v is not None else None
    return abs(p) / 1e6 if p else None


def app_name(comm, args):
    """A friendly name: Electron and Chromium helpers count as their app; everything else by its program name."""
    low = (args or comm).lower()
    for needle, name in (("vesktop", "Vesktop (Discord)"), ("discord", "Discord"), ("spotify", "Spotify"), ("zen", "Zen Browser"),
                         ("firefox", "Firefox"), ("chrom", "Chromium"), ("steam", "Steam"), ("java", "Java (Minecraft?)"),
                         ("horizon", "Horizon"), ("code", "VS Code"), ("claude", "Claude")):
        if needle in low:
            return name
    return comm


def busy_apps(rows):
    """[(cpu%, comm, args)] -> {app: cpu%} (only what is busy at all)."""
    out = {}
    for cpu, comm, args in rows:
        if cpu >= 1.0:
            name = app_name(comm, args)
            out[name] = out.get(name, 0.0) + cpu
    return out


def sample(now=None):
    """One reading while unplugged, appended to the log. Returns the record (or None)."""
    base = battery_dir()
    if base is None or sh.read_text(os.path.join(base, "status")) != "Discharging":
        return None
    watts = power_watts(base)
    if watts is None:
        return None
    rows = []
    for line in sh.out(["ps", "-eo", "pcpu,comm,args", "--sort=-pcpu", "--no-headers"], 5).splitlines()[:12]:
        parts = line.split(None, 2)
        if len(parts) >= 2:
            try:
                rows.append((float(parts[0]), parts[1], parts[2] if len(parts) > 2 else ""))
            except ValueError:
                pass
    record = {"t": now or time.time(), "w": round(watts, 2), "apps": {k: round(v, 1) for k, v in busy_apps(rows).items()},
              "pct": _num(os.path.join(base, "capacity"))}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    keep = record["t"] - KEEP_DAYS * 86400
    old = [r for r in read(LOG) if r["t"] >= keep]
    with open(LOG + ".tmp", "w", encoding="utf-8") as f:
        for r in old + [record]:
            f.write(json.dumps(r) + "\n")
    os.replace(LOG + ".tmp", LOG)
    return record


def read(path=None):
    out = []
    try:
        with open(path or LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def analyze(samples, full_wh=None, since=None):
    """{'avg_w', 'baseline_w', 'hours_left', 'apps': [(name, share 0..1)], 'minutes'} from the samples."""
    rows = [s for s in samples if since is None or s["t"] >= since]
    if not rows:
        return None
    avg = sum(r["w"] for r in rows) / len(rows)
    idle = sorted(r["w"] for r in rows if sum(r["apps"].values()) < IDLE_LOAD)
    baseline = idle[len(idle) // 5] if idle else avg * 0.4          # the quiet floor: the screen, the radios, the chips
    extra = {}
    for r in rows:
        total = sum(r["apps"].values())
        if total <= 0:
            continue
        above = max(0.0, r["w"] - baseline)
        for name, cpu in r["apps"].items():
            extra[name] = extra.get(name, 0.0) + above * cpu / total
    spent = sum(extra.values()) or 1.0
    apps = sorted(((n, v / spent) for n, v in extra.items()), key=lambda kv: -kv[1])
    return {"avg_w": avg, "baseline_w": baseline, "minutes": len(rows),
            "hours_left": (full_wh / avg) if full_wh and avg > 0 else None, "apps": apps}


def tips(result):
    out = []
    if not result:
        return ["Not enough yet: it needs a few minutes on battery."]
    for name, share in result["apps"][:3]:
        if share >= 0.25:
            out.append(f"{name} accounts for about {share * 100:.0f}% of the power above idle: close it when you are unplugged.")
    if result["baseline_w"] > 9:
        out.append(f"Even idle the laptop draws about {result['baseline_w']:.0f} W: lower the brightness, turn off Bluetooth you don't use, "
                   "and check that the NVIDIA chip is asleep (Settings > Graphics: Integrated).")
    if result["hours_left"] and result["hours_left"] < 3:
        out.append("At this rate a full battery lasts under 3 hours: Power saver mode helps (Settings > Power).")
    return out or ["Nothing stands out: the battery use looks normal."]


def full_wh():
    base = battery_dir()
    if not base:
        return None
    e = _num(os.path.join(base, "energy_full"))
    if e:
        return e / 1e6
    c, v = _num(os.path.join(base, "charge_full")), _num(os.path.join(base, "voltage_min_design"))
    return c * v / 1e12 if c and v else None


def report(as_json=False):
    result = analyze(read(), full_wh(), since=time.time() - 86400)
    if as_json:
        return json.dumps({"result": result, "tips": tips(result)}, ensure_ascii=False)
    if not result:
        return "\n".join(tips(None))
    lines = [f"On battery for {result['minutes']} minutes in the last day: about {result['avg_w']:.1f} W on average"
             + (f", so a full battery lasts about {result['hours_left']:.1f} hours" if result["hours_left"] else ""),
             f"Quiet baseline (screen, radios, chips): about {result['baseline_w']:.1f} W", "", "Who uses the battery (above that baseline):"]
    lines += [f"  {share * 100:4.0f}%  {name}" for name, share in result["apps"][:6]] or ["  (nothing stood out)"]
    lines += ["", *tips(result)]
    return "\n".join(lines)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "report"
    if mode == "report":
        print(report("--json" in argv))
    elif mode == "sample":
        print(json.dumps(sample()))
    else:
        print("usage: lennox-batterydoc report [--json] | sample", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
