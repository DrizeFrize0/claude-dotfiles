"""Network: find out what blocks things, a faster DNS, and the fixes.

    python3 -m lennox.net check              what is wrong and why (it tests; it changes nothing)
    python3 -m lennox.net fix [--yes]        what the fixes would be / do them
    python3 -m lennox.net dns bench          which DNS answers fastest from this laptop
    python3 -m lennox.net dns set NAME       cloudflare | google | quad9 | fastest   (all wired and Wi-Fi connections)
    python3 -m lennox.net dns apply          what Settings says (network.dns)
    python3 -m lennox.net dns reset          back to what the network hands out
    python3 -m lennox.net dns status

Lennox itself blocks nothing on the network. The one thing it can leave behind is focus mode's list of blocked
sites in /etc/hosts, which `fix` finds and removes (unless a focus session is running).
"""

import json
import os
import re
import socket
import statistics
import struct
import sys
import time
import urllib.error
import urllib.request

from . import settings as S
from . import sh

PROVIDERS = {
    "cloudflare": (["1.1.1.1", "1.0.0.1"], ["2606:4700:4700::1111", "2606:4700:4700::1001"]),
    "google": (["8.8.8.8", "8.8.4.4"], ["2001:4860:4860::8888", "2001:4860:4860::8844"]),
    "quad9": (["9.9.9.9", "149.112.112.112"], ["2620:fe::fe", "2620:fe::9"]),
}
DOMAINS = ["google.com", "youtube.com", "wikipedia.org", "github.com", "discord.com", "reddit.com", "amazon.com", "microsoft.com"]
SITES = ["https://www.google.com", "https://www.cloudflare.com", "https://discord.com", "https://github.com"]
HOSTS = os.environ.get("LENNOX_HOSTS_FILE", "/etc/hosts")
FOCUS_TOOL = os.environ.get("LENNOX_FOCUS_HOSTS_TOOL", "/usr/local/bin/lennox-focus-hosts")
FOCUS_MARK = "# >>> lennox focus"
# NetworkManager says "ethernet" and "wifi" in newer versions, "802-3-ethernet" and "802-11-wireless" in older ones
LINK_TYPES = ("ethernet", "wifi", "802-3-ethernet", "802-11-wireless")
WIRED = ("ethernet", "802-3-ethernet")


# ---------------------------------------------------------------- DNS on the wire

def build_query(name, qid):
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    labels = b"".join(bytes([len(p)]) + p.encode() for p in name.rstrip(".").split("."))
    return header + labels + b"\0" + struct.pack(">HH", 1, 1)


def parse_response(data, qid):
    """{'rcode', 'answers'} for a DNS answer to query `qid`, else None."""
    if len(data) < 12:
        return None
    rid, flags, _qd, an = struct.unpack(">HHHH", data[:8])
    if rid != qid or not flags & 0x8000:
        return None
    return {"rcode": flags & 0xF, "answers": an}


def query_time(server, name, timeout=1.5, port=53):
    """Seconds this DNS server takes to answer (None: no good answer)."""
    qid = int.from_bytes(os.urandom(2), "big")
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            t0 = time.monotonic()
            s.sendto(build_query(name, qid), (server, port))
            data, _addr = s.recvfrom(2048)
            took = time.monotonic() - t0
    except OSError:
        return None
    r = parse_response(data, qid)
    return took if r and r["rcode"] == 0 and r["answers"] > 0 else None


def bench(candidates, domains=DOMAINS, port=53, timeout=1.5):
    """candidates: [(label, ip)] -> [{'label', 'ip', 'ms', 'fails'}] fastest first."""
    rows = []
    for label, ip in candidates:
        times = [query_time(ip, d, timeout, port) for d in domains]
        good = [t for t in times if t is not None]
        rows.append({"label": label, "ip": ip, "ms": statistics.median(good) * 1000 if good else None,
                     "fails": len(times) - len(good)})
    return sorted(rows, key=lambda r: (r["fails"] > len(domains) // 3, r["ms"] if r["ms"] is not None else 1e9))


def gateway():
    out = sh.out(["ip", "route", "show", "default"], 3).split()
    return out[out.index("via") + 1] if "via" in out else ""


def candidates():
    found = []
    gw = gateway()
    if gw and ":" not in gw:
        found.append(("your router", gw))
    for name, (v4, _v6) in PROVIDERS.items():
        found.append((name, v4[0]))
    return found


# ---------------------------------------------------------------- NetworkManager

def _split(line):
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


def connections(active_only=False):
    """[(name, device, type)] of wired and Wi-Fi connections."""
    args = ["nmcli", "-t", "-f", "NAME,DEVICE,TYPE", "connection", "show"] + (["--active"] if active_only else [])
    out = []
    for line in sh.out(args, 5).splitlines():
        parts = _split(line)
        if len(parts) >= 3 and parts[2] in LINK_TYPES:
            out.append((parts[0], parts[1], parts[2]))
    return out


def set_dns(provider):
    """Fixed DNS servers for every wired and Wi-Fi connection (and now, without dropping the connection)."""
    v4, v6 = PROVIDERS[provider]
    done = []
    for name, _dev, _t in connections():
        code, _o, err = sh.run(["nmcli", "connection", "modify", name, "ipv4.dns", " ".join(v4), "ipv4.ignore-auto-dns", "yes",
                                "ipv6.dns", " ".join(v6), "ipv6.ignore-auto-dns", "yes"], 15)
        if code == 0:
            done.append(name)
        else:
            print(f"Couldn't change {name}: {err.strip()}", file=sys.stderr)
    for _name, dev, _t in connections(active_only=True):
        if dev:
            sh.run(["nmcli", "device", "reapply", dev], 15)
    return done


def reset_dns():
    done = []
    for name, dev, _t in connections():
        code, _o, _e = sh.run(["nmcli", "connection", "modify", name, "ipv4.dns", "", "ipv4.ignore-auto-dns", "no",
                               "ipv6.dns", "", "ipv6.ignore-auto-dns", "no"], 15)
        if code == 0:
            done.append(name)
    for _name, dev, _t in connections(active_only=True):
        if dev:
            sh.run(["nmcli", "device", "reapply", dev], 15)
    return done


def find_mtu(works, high=1472, low=1200):
    """The biggest ping payload that gets through (works(size) -> bool), by halving. The connection's MTU is that + 28.
    None if even the smallest fails (then it isn't a size problem)."""
    if not works(low):
        return None
    lo, hi = low, high
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if works(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo + 28


def ping_df(size, host="1.1.1.1"):
    return sh.run(["ping", "-c", "1", "-W", "2", "-M", "do", "-s", str(size), host], 6)[0] == 0


def set_mtu(mtu):
    """Sets the MTU on the active wired and Wi-Fi connections, and applies it now."""
    done = []
    for name, dev, kind in connections(active_only=True):
        prop = "802-3-ethernet.mtu" if kind in WIRED else "802-11-wireless.mtu"
        if sh.run(["nmcli", "connection", "modify", name, prop, str(mtu)], 15)[0] == 0:
            done.append(name)
            if dev:
                sh.run(["nmcli", "device", "reapply", dev], 15)
    return done


def disable_ipv6(name):
    code, _o, _e = sh.run(["nmcli", "connection", "modify", name, "ipv6.method", "disabled"], 15)
    return code == 0


# ---------------------------------------------------------------- what is wrong

def focus_block_present(text):
    return FOCUS_MARK in text


def focus_active():
    try:
        with open(os.path.join(S.STATE_DIR, "focus.json"), encoding="utf-8") as f:
            return json.load(f).get("phase") == "focus"
    except (OSError, ValueError, AttributeError):
        return False


def remove_focus_block():
    """The stuck block comes out through the same root helper focus mode itself uses."""
    return sh.run(["pkexec", FOCUS_TOOL, "off"], 20)[0] == 0


def tcp_ok(host, port=443, timeout=3):
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except OSError:
        return False


def https_ok(url, timeout=6):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Lennox"})
        with urllib.request.urlopen(req, timeout=timeout):                    # noqa: S310  fixed https addresses
            return True
    except urllib.error.HTTPError:
        return True                                                           # the site answered: not blocked
    except (OSError, ValueError):
        return False


def system_dns_ms(domain="github.com"):
    t0 = time.monotonic()
    try:
        socket.getaddrinfo(domain, 443, socket.AF_INET)
    except OSError:
        return None
    return (time.monotonic() - t0) * 1000


def link_info():
    """Wired devices: [{'dev', 'up', 'speed', 'duplex'}]"""
    out = []
    base = "/sys/class/net"
    try:
        devs = sorted(os.listdir(base))
    except OSError:
        return out
    for dev in devs:
        if not (dev.startswith(("en", "eth")) and os.path.isdir(os.path.join(base, dev, "device"))):
            continue
        speed = sh.read_text(os.path.join(base, dev, "speed"))
        out.append({"dev": dev, "up": sh.read_text(os.path.join(base, dev, "operstate")) == "up",
                    "speed": int(speed) if speed.lstrip("-").isdigit() else None, "duplex": sh.read_text(os.path.join(base, dev, "duplex"))})
    return out


def snapshot():
    try:
        with open(HOSTS, encoding="utf-8") as f:
            hosts = f.read()
    except OSError:
        hosts = ""
    v6_addr = bool(sh.out(["ip", "-6", "addr", "show", "scope", "global"], 3))
    return {
        "hosts_blocked": focus_block_present(hosts), "focus_active": focus_active(),
        "system_dns_ms": system_dns_ms(), "public_dns_ok": query_time("1.1.1.1", "google.com") is not None,
        "ip_ok": tcp_ok("1.1.1.1"), "sites": {u: https_ok(u) for u in SITES},
        "ipv6_addr": v6_addr, "ipv6_ok": tcp_ok("2606:4700:4700::1111") if v6_addr else None,
        "mtu_ok": ping_df(1472), "mtu_best": None,
        "links": link_info(), "proxy": [k for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") if os.environ.get(k)],
        "firewalls": [u for u in ("ufw", "firewalld", "nftables", "iptables") if sh.out(["systemctl", "is-active", u], 3) == "active"],
    }


def diagnose(s):
    """[(problem, what it means / what to do, fixable by `lennox-net fix`?)] from a snapshot."""
    out = []
    if s["hosts_blocked"] and not s["focus_active"]:
        out.append(("Sites are blocked on this laptop by Lennox's focus mode (a list in /etc/hosts that was never taken out)",
                    "Nothing to do with your network: lennox-net fix removes it", True))
    elif s["hosts_blocked"]:
        out.append(("A focus session is running, so its sites are blocked on purpose", "Stop it: lennox-focus stop", False))
    if not s["ip_ok"]:
        out.append(("No connection to the internet at all (even by number)", "Check the cable and the router; run: nmcli device status", False))
    else:
        if s["system_dns_ms"] is None and s["public_dns_ok"]:
            out.append(("This laptop can't look up names with the DNS it was given, but a public DNS works",
                        "Switch to a public DNS: lennox-net fix", True))
        elif s["system_dns_ms"] is not None and s["system_dns_ms"] > 150:
            out.append((f"Looking up a name takes {s['system_dns_ms']:.0f} ms (slow)", "A faster DNS: lennox-net fix", True))
        failed = [u for u, ok in s["sites"].items() if not ok]
        if failed and len(failed) < len(s["sites"]):
            out.append((f"Some sites don't open: {', '.join(u.split('//')[1] for u in failed)}",
                        "Often IPv6 or a packet-size problem on this cable: see below", False))
        elif failed:
            out.append(("No site opens, although the connection works", "Probably the DNS or a proxy: lennox-net fix", True))
        if s["ipv6_addr"] and s["ipv6_ok"] is False:
            out.append(("IPv6 is set up but doesn't work (sites try it first, wait, then fall back: slow or 'blocked')",
                        "Turn IPv6 off for this connection: lennox-net fix", True))
        if not s["mtu_ok"]:
            best = s.get("mtu_best")
            out.append(("Big packets don't get through: this connection can only carry smaller ones than normal"
                        + (f" (the biggest that works: {best})" if best else ""),
                        "Some sites hang halfway or load only partly. " + ("lennox-net fix sets that size on this laptop" if best
                                                                           else "Set the router's MTU to 1500, or check the cable"), bool(best)))
    for link in s["links"]:
        if link["up"] and link["speed"] is not None and 0 < link["speed"] < 1000:
            out.append((f"The cable runs at only {link['speed']} Mb/s on {link['dev']}", "A damaged cable or a worn port: try another cable", False))
        if link["up"] and link["duplex"] == "half":
            out.append((f"The cable is in half duplex on {link['dev']}", "That causes drops and slowness: try another cable or port", False))
    if s["proxy"]:
        out.append((f"A proxy is set in the environment ({', '.join(s['proxy'])})", "Programs started from here go through it: unset it", False))
    if s["firewalls"]:
        out.append((f"A firewall is running here: {', '.join(s['firewalls'])}", "Lennox doesn't change it. See its rules: sudo ufw status, or sudo nft list ruleset", False))
    return out


def report(s):
    found = diagnose(s)
    lines = ["Connection:"]
    for link in s["links"]:
        lines.append(f"  {link['dev']}: {'connected' if link['up'] else 'no cable'}" + (f", {link['speed']} Mb/s {link['duplex']}" if link["up"] and link["speed"] else ""))
    lines.append(f"  internet: {'yes' if s['ip_ok'] else 'NO'}  ·  looking up a name: " + (f"{s['system_dns_ms']:.0f} ms" if s["system_dns_ms"] is not None else "fails")
                 + "  ·  IPv6: " + ("works" if s["ipv6_ok"] else "broken" if s["ipv6_ok"] is False else "none"))
    lines.append("  sites: " + ", ".join(f"{u.split('//')[1]} {'ok' if ok else 'BLOCKED'}" for u, ok in s["sites"].items()))
    lines += ["", "What I found:"]
    lines += [f"  - {p}\n      -> {w}" for p, w, _f in found] or ["  - Nothing is wrong that I can see"]
    if any(f for _p, _w, f in found):
        lines += ["", "Fix it: lennox-net fix --yes"]
    return "\n".join(lines)


def plan_fix(s):
    """The steps `fix` would do, from a snapshot: [(key, text)]."""
    steps = []
    if s["hosts_blocked"] and not s["focus_active"]:
        steps.append(("hosts", "Take focus mode's leftover site block out of /etc/hosts"))
    if (s["system_dns_ms"] is None and s["public_dns_ok"]) or (s["system_dns_ms"] or 0) > 150 or any(not ok for ok in s["sites"].values()):
        steps.append(("dns", "Use the fastest DNS for every wired and Wi-Fi connection"))
    if s["ipv6_addr"] and s["ipv6_ok"] is False:
        steps.append(("ipv6", "Turn IPv6 off on the connections (it is set up but doesn't work)"))
    if not s["mtu_ok"] and s.get("mtu_best"):
        steps.append(("mtu", f"Use the packet size that works on this connection (MTU {s['mtu_best']}) so nothing hangs halfway"))
    return steps


def apply_dns_choice(choice):
    """choice: auto | fastest | a provider name."""
    if choice == "auto":
        return reset_dns(), "automatic (what the network hands out)"
    if choice == "fastest":
        ranked = [r for r in bench(candidates()) if r["label"] in PROVIDERS]       # a router's DNS can't be set on other networks
        choice = ranked[0]["label"] if ranked else "cloudflare"
    return set_dns(choice), choice


def main(argv):
    mode = argv[1] if len(argv) > 1 else "check"
    if mode == "check":
        s = snapshot()
        if not s["mtu_ok"]:
            s["mtu_best"] = find_mtu(ping_df)
        print(report(s))
    elif mode == "fix":
        s = snapshot()
        if not s["mtu_ok"]:
            print("Measuring the packet size that works…")
            s["mtu_best"] = find_mtu(ping_df)
        steps = plan_fix(s)
        if not steps:
            print("Nothing to fix.")
            return 0
        print("\n".join(f"  - {t}" for _k, t in steps))
        if "--yes" not in argv:
            print("\nNothing was changed. To do it: lennox-net fix --yes")
            return 0
        for key, _t in steps:
            if key == "hosts":
                print("Block removed." if remove_focus_block() else "Couldn't remove the block (needs your approval: run again).")
            elif key == "dns":
                done, name = apply_dns_choice("fastest")
                print(f"DNS: {name} on {len(done)} connection(s).")
                S.set_value("network.dns", "fastest")
            elif key == "ipv6":
                names = [n for n, _d, _t in connections(active_only=True) if disable_ipv6(n)]
                print("IPv6 off on: " + ", ".join(names) if names else "No active connection to change (is the cable connected?)")
            elif key == "mtu":
                names = set_mtu(s["mtu_best"])
                print(f"Packet size {s['mtu_best']} on: " + ", ".join(names) if names else "No active connection to change")
    elif mode == "dns":
        sub = argv[2] if len(argv) > 2 else "status"
        if sub == "bench":
            for r in bench(candidates()):
                print(f"  {r['label']:12} {r['ip']:16} " + (f"{r['ms']:5.1f} ms" if r["ms"] is not None else "no answer") + f"  ({r['fails']} failed)")
        elif sub in ("set", "apply", "reset"):
            choice = "auto" if sub == "reset" else (argv[3] if sub == "set" and len(argv) > 3 else S.load()["network"]["dns"])
            if sub == "set" and choice not in (*PROVIDERS, "fastest", "auto"):
                print("usage: lennox-net dns set cloudflare|google|quad9|fastest", file=sys.stderr)
                return 2
            done, name = apply_dns_choice(choice)
            print(f"DNS: {name} on {len(done)} connection(s).")
            if sub == "set":
                S.set_value("network.dns", choice)
        else:
            print(sh.out(["resolvectl", "status"], 5) or sh.out(["cat", "/etc/resolv.conf"], 3))
    else:
        print("usage: lennox-net check | fix [--yes] | dns bench|set NAME|apply|reset|status", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
