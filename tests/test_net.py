"""lennox-net: DNS on the wire, ranking, diagnosis, the leftover focus block, NetworkManager changes."""
import os
import socket
import stat
import struct
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import net  # noqa: E402


def fake_dns(delay=0.0, rcode=0, answers=1):
    """A DNS server on a local port that answers every query after `delay` seconds. Returns (port, stop)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.2)
    running = [True]

    def serve():
        while running[0]:
            try:
                data, addr = sock.recvfrom(512)
            except OSError:
                continue
            time.sleep(delay)
            qid = struct.unpack(">H", data[:2])[0]
            sock.sendto(struct.pack(">HHHHHH", qid, 0x8180 | rcode, 1, answers, 0, 0) + data[12:], addr)
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return sock.getsockname()[1], lambda: (running.__setitem__(0, False), sock.close())


class Wire(unittest.TestCase):
    def test_query_and_response(self):
        q = net.build_query("example.com", 0x1234)
        self.assertEqual(q[:2], b"\x12\x34")
        self.assertIn(b"\x07example\x03com\x00", q)
        reply = struct.pack(">HHHHHH", 0x1234, 0x8180, 1, 1, 0, 0) + q[12:]
        self.assertEqual(net.parse_response(reply, 0x1234), {"rcode": 0, "answers": 1})
        self.assertIsNone(net.parse_response(reply, 0x9999))                # someone else's answer
        self.assertIsNone(net.parse_response(b"short", 1))

    def test_timing_and_failures(self):
        port, stop = fake_dns(delay=0.05)
        try:
            t = net.query_time("127.0.0.1", "x.test", 1.0, port)
            self.assertTrue(0.04 < t < 0.5)
        finally:
            stop()
        port, stop = fake_dns(rcode=3)                                       # NXDOMAIN counts as no good answer
        try:
            self.assertIsNone(net.query_time("127.0.0.1", "x.test", 1.0, port))
        finally:
            stop()
        self.assertIsNone(net.query_time("127.0.0.1", "x.test", 0.2, 9))      # nothing listens

    def test_ranking(self):
        fast, stop_fast = fake_dns(0.0)
        slow, stop_slow = fake_dns(0.08)
        try:
            rows = []
            for label, port in (("slow", slow), ("fast", fast)):
                rows += net.bench([(label, "127.0.0.1")], ["a.test", "b.test", "c.test"], port=port, timeout=1.0)
            ranked = sorted(rows, key=lambda r: r["ms"])
            self.assertEqual([r["label"] for r in ranked], ["fast", "slow"])
            dead = net.bench([("dead", "127.0.0.1")], ["a.test"], port=9, timeout=0.2)[0]
            self.assertEqual((dead["ms"], dead["fails"]), (None, 1))
        finally:
            stop_fast()
            stop_slow()


def snap(**kw):
    base = {"hosts_blocked": False, "focus_active": False, "system_dns_ms": 20.0, "public_dns_ok": True, "ip_ok": True,
            "sites": {"https://www.google.com": True, "https://discord.com": True}, "ipv6_addr": True, "ipv6_ok": True, "mtu_ok": True,
            "links": [{"dev": "enp3s0", "up": True, "speed": 1000, "duplex": "full"}], "proxy": [], "firewalls": []}
    base.update(kw)
    return base


def text(s):
    return " | ".join(f"{p} -> {w}" for p, w, _f in net.diagnose(s))


class Diagnose(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(net.diagnose(snap()), [])

    def test_leftover_focus_block(self):
        d = net.diagnose(snap(hosts_blocked=True))
        self.assertIn("focus mode", d[0][0])
        self.assertTrue(d[0][2])
        self.assertIn("running", text(snap(hosts_blocked=True, focus_active=True)))      # on purpose during a session

    def test_dns_problems(self):
        self.assertIn("can't look up names", text(snap(system_dns_ms=None)))
        self.assertIn("slow", text(snap(system_dns_ms=400.0)))
        self.assertNotIn("slow", text(snap(system_dns_ms=40.0)))

    def test_broken_ipv6(self):
        self.assertIn("IPv6 is set up but doesn't work", text(snap(ipv6_ok=False)))
        self.assertNotIn("IPv6", text(snap(ipv6_addr=False, ipv6_ok=None)))

    def test_partly_blocked_sites_and_no_internet(self):
        self.assertIn("Some sites don't open: discord.com", text(snap(sites={"https://www.google.com": True, "https://discord.com": False})))
        self.assertIn("No connection to the internet", text(snap(ip_ok=False)))

    def test_bad_cable_and_firewall_and_proxy(self):
        t = text(snap(links=[{"dev": "enp3s0", "up": True, "speed": 100, "duplex": "half"}], firewalls=["ufw"], proxy=["https_proxy"]))
        for word in ("100 Mb/s", "half duplex", "ufw", "proxy"):
            self.assertIn(word, t)

    def test_plan_only_what_is_needed(self):
        self.assertEqual(net.plan_fix(snap()), [])
        keys = [k for k, _t in net.plan_fix(snap(hosts_blocked=True, system_dns_ms=None, ipv6_ok=False))]
        self.assertEqual(keys, ["hosts", "dns", "ipv6"])
        self.assertEqual([k for k, _t in net.plan_fix(snap(hosts_blocked=True, focus_active=True))], [])


class FocusBlock(unittest.TestCase):
    def test_marker(self):
        self.assertTrue(net.focus_block_present("127.0.0.1 localhost\n# >>> lennox focus (sites blocked while focusing) >>>\n0.0.0.0 youtube.com\n"))
        self.assertFalse(net.focus_block_present("127.0.0.1 localhost\n"))


class NetworkManager(unittest.TestCase):
    def test_dns_commands(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "calls")
            tool = os.path.join(d, "nmcli")
            with open(tool, "w", encoding="utf-8") as f:
                f.write(f'''#!/bin/sh
echo "$@" >> {log}
case "$*" in
  *"connection show --active"*) printf 'Wired connection 1:enp3s0:802-3-ethernet\\nHome\\\\: Wi-Fi:wlan0:802-11-wireless\\nlo:lo:loopback\\n' ;;
  *"connection show"*) printf 'Wired connection 1:enp3s0:802-3-ethernet\\nHome\\\\: Wi-Fi:wlan0:802-11-wireless\\nvpn:--:wireguard\\n' ;;
esac
''')
            os.chmod(tool, os.stat(tool).st_mode | stat.S_IEXEC)
            old = os.environ["PATH"]
            os.environ["PATH"] = d + ":" + old
            try:
                done = net.set_dns("cloudflare")
                calls = open(log, encoding="utf-8").read()
            finally:
                os.environ["PATH"] = old
        self.assertEqual(done, ["Wired connection 1", "Home: Wi-Fi"])             # the VPN and loopback are left alone
        self.assertIn("connection modify Wired connection 1 ipv4.dns 1.1.1.1 1.0.0.1 ipv4.ignore-auto-dns yes", calls)
        self.assertIn("ipv6.dns 2606:4700:4700::1111 2606:4700:4700::1001", calls)
        self.assertIn("device reapply enp3s0", calls)
        self.assertNotIn("wireguard", calls)


if __name__ == "__main__":
    unittest.main()
