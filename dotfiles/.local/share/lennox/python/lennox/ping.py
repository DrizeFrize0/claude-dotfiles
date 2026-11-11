"""Check your ping: to your router, to the internet and to your Minecraft server, with what to do about it.

    python3 -m lennox.ping [--json]

Low ping and steady ping (little jitter, no loss) matter more in games than speed.
"""

import json
import re
import sys

from . import settings as S
from . import sh

RTT = re.compile(r"=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms")
LOSS = re.compile(r"([\d.]+)% packet loss")


def parse_ping(text):
    """`ping` output -> {'avg', 'min', 'max', 'jitter', 'loss'} (numbers in ms and %), or None if nothing answered."""
    loss = LOSS.search(text)
    rtt = RTT.search(text)
    if not rtt:
        return None
    return {"min": float(rtt.group(1)), "avg": float(rtt.group(2)), "max": float(rtt.group(3)),
            "jitter": float(rtt.group(4)), "loss": float(loss.group(1)) if loss else 0.0}


def ping(host, count=8):
    code, out, _err = sh.run(["ping", "-c", str(count), "-i", "0.2", "-W", "1", host], count + 6)
    return parse_ping(out)


def gateway():
    out = sh.out(["ip", "route", "show", "default"], 3).split()
    return out[out.index("via") + 1] if "via" in out else ""


def wifi():
    """{'ssid', 'signal', 'ghz'} of the connected Wi-Fi, or None (cable or no Wi-Fi)."""
    for line in sh.out(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,FREQ", "dev", "wifi"], 4).splitlines():
        if line.startswith("*:"):
            parts = line.replace("\\:", "\0").split(":")
            if len(parts) >= 4 and parts[2].isdigit():
                freq = re.sub(r"\D", "", parts[3]) or "0"
                return {"ssid": parts[1].replace("\0", ":"), "signal": int(parts[2]), "ghz": 5 if int(freq) >= 4900 else 2.4}
    return None


def power_save():
    """True/False if Wi-Fi power saving is on/off (it adds lag), None if unknown."""
    for line in sh.out(["iw", "dev"], 3).splitlines():
        if line.strip().startswith("Interface"):
            text = sh.out(["iw", "dev", line.split()[1], "get", "power_save"], 3).lower()
            if "on" in text:
                return True
            if "off" in text:
                return False
    return None


def advice(results, wifi_info, saving):
    """Plain sentences: what to do, from the measurements."""
    tips = []
    router, net = results.get("router"), results.get("internet")
    if wifi_info:
        if wifi_info["signal"] < 55:
            tips.append(f"Your Wi-Fi signal is weak ({wifi_info['signal']}%). Move closer to the router, or use a cable.")
        if wifi_info["ghz"] == 2.4:
            tips.append("You're on the 2.4 GHz Wi-Fi, which is crowded and laggy. Connect to the 5 GHz one if your router has it.")
    if saving:
        tips.append("Wi-Fi power saving is on, which adds lag. Run: lennox upgrade (it turns it off).")
    if router and router["avg"] > 15:
        tips.append(f"Even your router takes {router['avg']:.0f} ms to answer: the problem is the Wi-Fi in your home, not the internet.")
    if router and router["jitter"] > 8:
        tips.append("Your connection to the router is bumpy (big ups and downs). Other devices using the Wi-Fi, or distance, can cause that.")
    if net and router and net["avg"] - router["avg"] > 60:
        tips.append("The internet part is slow. Ask your provider, or try a cable.")
    if any(r and r["loss"] > 0 for r in results.values()):
        tips.append("Some packets got lost. That causes rubber-banding in games.")
    return tips or ["Your connection looks good for gaming."]


def run_check():
    settings = S.load()
    host = settings["games"]["mc_server"].strip()
    results = {}
    gw = gateway()
    if gw:
        results["router"] = ping(gw)
    results["internet"] = ping("1.1.1.1")
    if host:
        results["server"] = ping(host)
    info = wifi()
    saving = power_save()
    return {"results": results, "wifi": info, "power_save": saving, "server": host, "advice": advice(results, info, saving)}


def format_text(report):
    names = {"router": "Router", "internet": "Internet (1.1.1.1)", "server": report.get("server") or "Server"}
    lines = []
    for key, data in report["results"].items():
        lines.append(f"{names[key]:20} " + (f"{data['avg']:.0f} ms  (jitter {data['jitter']:.1f}, lost {data['loss']:.0f}%)" if data else "no answer"))
    lines += ["", *report["advice"]]
    return "\n".join(lines)


def main(argv):
    report = run_check()
    print(json.dumps(report) if "--json" in argv else format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
