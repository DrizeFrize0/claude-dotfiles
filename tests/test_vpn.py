"""VPN profiles: import (ovpn, conf, zip), connect, disconnect, with a pretend nmcli. Run: python3 tests/test_vpn.py"""
import os
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import vpn  # noqa: E402

FAKE = r'''#!/usr/bin/env python3
import os, sys
state = os.environ["FAKE_NM"]
def read(name):
    p = os.path.join(state, name)
    return open(p).read().splitlines() if os.path.exists(p) else []
def write(name, lines):
    open(os.path.join(state, name), "w").write("\n".join(lines) + ("\n" if lines else ""))
a = sys.argv[1:]
if "connection" in a:
    a = a[a.index("connection"):]
open(os.path.join(state, "calls"), "a").write(" ".join(a) + "\n")
if a[:2] == ["connection", "show"]:
    items = read("profiles")
    if "--active" in a:
        act = read("active")
        items = [i for i in items if i.rsplit(":", 1)[0] in act]
    print("\n".join(items + ["Wired connection 1:802-3-ethernet"]))
elif a[:2] == ["connection", "import"]:
    kind, path = a[3], a[5]
    name = os.path.splitext(os.path.basename(path))[0]
    write("profiles", read("profiles") + [name + ":" + ("wireguard" if kind == "wireguard" else "vpn")])
elif a[:2] == ["connection", "up"]:
    write("active", read("active") + [a[2]])
elif a[:2] == ["connection", "down"]:
    write("active", [x for x in read("active") if x != a[2]])
elif a[:2] == ["connection", "delete"]:
    write("profiles", [x for x in read("profiles") if not x.startswith(a[2] + ":")])
'''

OVPN_LOGIN = "client\nremote vpn.example.com 443\nauth-user-pass\n"
OVPN_FILE = "client\nremote x 1\nauth-user-pass /etc/creds\n"


class VpnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        path = os.path.join(self.bin, "nmcli")
        with open(path, "w") as f:
            f.write(FAKE)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        os.environ["PATH"] = self.bin + os.pathsep + os.environ["PATH"]
        os.environ["FAKE_NM"] = self.tmp

    def calls(self):
        with open(os.path.join(self.tmp, "calls")) as f:
            return f.read().splitlines()

    def test_parsing(self):
        self.assertTrue(vpn.needs_login(OVPN_LOGIN))
        self.assertFalse(vpn.needs_login(OVPN_FILE))
        self.assertFalse(vpn.needs_login("# auth-user-pass\nclient\n"))
        self.assertEqual(vpn.parse_connections("a b:vpn\nwifi:802-11-wireless\nwg0:wireguard\nx\\:y:vpn\n"),
                         [("a b", "openvpn"), ("wg0", "wireguard"), ("x:y", "openvpn")])
        self.assertEqual(vpn.kind_of("a.OVPN"), "openvpn")
        self.assertEqual(vpn.kind_of("a.conf"), "wireguard")
        self.assertIsNone(vpn.kind_of("a.txt"))

    def test_zip_import_is_safe_and_logs_in(self):
        z = os.path.join(self.tmp, "vpnbook.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("vpnbook-de20-tcp443.ovpn", OVPN_LOGIN)
            zf.writestr("vpnbook-us1-udp53.ovpn", OVPN_LOGIN)
            zf.writestr("../../escape.ovpn", OVPN_LOGIN)       # must land only as a plain name, never outside
            zf.writestr("readme.txt", "hi")
        names, problems = vpn.import_file(z, "vpnbook", "pw123")
        self.assertEqual(problems, [])
        self.assertEqual(sorted(names), ["escape", "vpnbook-de20-tcp443", "vpnbook-us1-udp53"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escape.ovpn")))
        modify = [c for c in self.calls() if c.startswith("connection modify vpnbook-de20-tcp443")]
        self.assertIn("connection modify vpnbook-de20-tcp443 connection.autoconnect no", modify)
        self.assertIn("connection modify vpnbook-de20-tcp443 +vpn.data username=vpnbook", modify)
        self.assertIn("connection modify vpnbook-de20-tcp443 vpn.secrets password=pw123", modify)

    def test_single_files_and_problems(self):
        conf = os.path.join(self.tmp, "wg-home.conf")
        open(conf, "w").write("[Interface]\n")
        self.assertEqual(vpn.import_file(conf), (["wg-home"], []))
        self.assertEqual(vpn.list_profiles(), [("wg-home", "wireguard")])
        txt = os.path.join(self.tmp, "a.txt")
        open(txt, "w").write("x")
        self.assertEqual(vpn.import_file(txt)[0], [])
        self.assertTrue(vpn.import_file(os.path.join(self.tmp, "missing.ovpn"))[1])
        empty = os.path.join(self.tmp, "empty.zip")
        zipfile.ZipFile(empty, "w").close()
        self.assertIn("no .ovpn", vpn.import_file(empty)[1][0])

    def test_connect_disconnect_remove(self):
        f = os.path.join(self.tmp, "office.ovpn")
        open(f, "w").write(OVPN_FILE)
        vpn.import_file(f)
        self.assertEqual(vpn.active_vpns(), [])
        self.assertTrue(vpn.connect("office")[0])
        self.assertEqual(vpn.active_vpns(), ["office"])
        self.assertEqual(vpn.disconnect(), ["office"])
        self.assertEqual(vpn.active_vpns(), [])
        self.assertTrue(vpn.remove("office"))
        self.assertEqual(vpn.list_profiles(), [])


if __name__ == "__main__":
    unittest.main()
