"""VPN profiles for the whole laptop, through NetworkManager.

    python3 -m lennox.vpn import FILE [--user U] [--password P]   OpenVPN (.ovpn), WireGuard (.conf) or a .zip of them
    python3 -m lennox.vpn list | status | connect NAME | disconnect | remove NAME

Free providers like VPNBook hand out .ovpn files plus a username and password on their website:
import the file (or the whole zip) and give those two.
"""

import os
import sys
import tempfile
import zipfile

from . import sh

KINDS = {".ovpn": "openvpn", ".conf": "wireguard"}


def kind_of(path):
    return KINDS.get(os.path.splitext(path)[1].lower())


def needs_login(ovpn_text):
    """OpenVPN files that ask for a username and password say `auth-user-pass` without a file after it."""
    for line in ovpn_text.splitlines():
        parts = line.split("#")[0].split(";")[0].split()
        if parts[:1] == ["auth-user-pass"] and len(parts) == 1:
            return True
    return False


def parse_connections(text):
    """`nmcli -t -f NAME,TYPE connection show` lines -> [(name, 'openvpn'|'wireguard')]."""
    out = []
    for line in text.splitlines():
        name, _, kind = line.rpartition(":")
        name = name.replace("\\:", ":")
        if kind in ("vpn", "wireguard"):
            out.append((name, "wireguard" if kind == "wireguard" else "openvpn"))
    return out


def safe_members(zf):
    """The VPN files inside a zip, by base name only (a zip can't write anywhere else)."""
    names = {}
    for info in zf.infolist():
        base = os.path.basename(info.filename)
        if base and not info.is_dir() and kind_of(base) and info.file_size < 5_000_000:
            names[base] = info
    return names


def nmcli(*args, timeout=30):
    return sh.run(["nmcli", *args], timeout)


def list_profiles():
    code, out, _ = nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    return parse_connections(out) if code == 0 else []


def active():
    code, out, _ = nmcli("-t", "-f", "NAME,TYPE", "connection", "show", "--active")
    return [n for n, _k in parse_connections(out)] if code == 0 else []


def _import_one(path, user, password):
    kind = kind_of(path)
    if not kind:
        return None, f"{os.path.basename(path)}: not a .ovpn or .conf file"
    before = {n for n, _k in list_profiles()}
    code, _out, err = nmcli("connection", "import", "type", kind, "file", path)
    if code != 0:
        return None, (err.strip() or "import failed").splitlines()[-1]
    added = [n for n, _k in list_profiles() if n not in before]
    if not added:
        return None, "imported, but the profile did not appear"
    name = added[0]
    nmcli("connection", "modify", name, "connection.autoconnect", "no")
    if kind == "openvpn":
        with open(path, encoding="utf-8", errors="replace") as f:
            asks = needs_login(f.read())
        if asks and user:
            # Stored by NetworkManager for this user (password-flags 0 = save it)
            nmcli("connection", "modify", name, "+vpn.data", "password-flags=0")
            nmcli("connection", "modify", name, "+vpn.data", f"username={user}")
            if password:
                nmcli("connection", "modify", name, "vpn.secrets", f"password={password}")
    return name, None


def import_file(path, user=None, password=None):
    """Imports a file or a zip. Returns ([names], [problems])."""
    names, problems = [], []
    if not os.path.exists(path):
        return names, [f"{path}: no such file"]
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
            for base, info in sorted(safe_members(zf).items()):
                target = os.path.join(tmp, base)
                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                name, problem = _import_one(target, user, password)
                (names if name else problems).append(name or problem)
            if not names and not problems:
                problems.append("no .ovpn or .conf files in the zip")
    else:
        name, problem = _import_one(path, user, password)
        (names if name else problems).append(name or problem)
    return names, problems


def connect(name):
    code, out, err = nmcli("connection", "up", name, timeout=60)
    return code == 0, (out if code == 0 else err).strip()


def disconnect():
    names = active_vpns()
    for n in names:
        nmcli("connection", "down", n)
    return names


def active_vpns():
    vpn = {n for n, _k in list_profiles()}
    return [n for n in active() if n in vpn]


def remove(name):
    return nmcli("connection", "delete", name)[0] == 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "import" and len(argv) > 2:
        user = password = None
        rest = argv[3:]
        for i, a in enumerate(rest):
            if a == "--user" and i + 1 < len(rest):
                user = rest[i + 1]
            if a == "--password" and i + 1 < len(rest):
                password = rest[i + 1]
        names, problems = import_file(os.path.expanduser(argv[2]), user, password)
        for n in names:
            print(f"Imported: {n}")
        for p in problems:
            print(f"Problem: {p}", file=sys.stderr)
        return 0 if names else 1
    if cmd == "list":
        for name, kind in list_profiles():
            print(f"{name}\t{kind}")
    elif cmd == "status":
        now = active_vpns()
        print("Connected: " + ", ".join(now) if now else "Not connected")
    elif cmd == "connect" and len(argv) > 2:
        ok, msg = connect(" ".join(argv[2:]))
        print(msg)
        return 0 if ok else 1
    elif cmd == "disconnect":
        done = disconnect()
        print("Disconnected: " + ", ".join(done) if done else "Not connected")
    elif cmd == "remove" and len(argv) > 2:
        return 0 if remove(" ".join(argv[2:])) else 1
    else:
        print("usage: lennox-vpn import FILE [--user U --password P] | list | status | connect NAME | disconnect | remove NAME", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
