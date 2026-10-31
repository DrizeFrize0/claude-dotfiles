"""Your Minecraft server in the bar: online, players (with names), ping, joins.

    python3 -m lennox.mcserver waybar|status [ADDRESS]

Asks the server the same way the multiplayer screen does (Server List Ping),
following the _minecraft._tcp SRV record like the game. When someone joins,
you get a notification (Lennox Settings > Game center).
"""

import json
import os
import random
import re
import socket
import struct
import subprocess
import sys
import time

from . import settings as S

STATE = os.path.join(S.CACHE_DIR, "mcserver.json")
TIMEOUT = 4


# ---------------------------------------------------------------- DNS SRV

def _nameserver(path="/etc/resolv.conf"):
    try:
        with open(path) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except OSError:
        pass
    return "127.0.0.53"


def _skip_name(packet, i):
    while True:
        length = packet[i]
        if length == 0:
            return i + 1
        if length & 0xC0 == 0xC0:      # compressed pointer
            return i + 2
        i += length + 1


def _read_name(packet, i):
    labels = []
    while True:
        length = packet[i]
        if length == 0:
            break
        if length & 0xC0 == 0xC0:
            pointer = struct.unpack(">H", packet[i:i + 2])[0] & 0x3FFF
            labels.append(_read_name(packet, pointer))
            break
        labels.append(packet[i + 1:i + 1 + length].decode("ascii", "replace"))
        i += length + 1
    return ".".join(x for x in labels if x)


def srv_lookup(host, nameserver=None):
    """(target, port) from _minecraft._tcp.HOST, or None."""
    qid = random.randint(0, 0xFFFF)
    name = f"_minecraft._tcp.{host}"
    question = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.split(".")) + b"\0"
    packet = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + question + struct.pack(">HH", 33, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.sendto(packet, (nameserver or _nameserver(), 53))
            reply, _ = s.recvfrom(2048)
    except (OSError, UnicodeError):
        return None
    if len(reply) < 12 or struct.unpack(">H", reply[:2])[0] != qid:
        return None
    _, flags, qd, an, _, _ = struct.unpack(">HHHHHH", reply[:12])
    if flags & 0x000F or an == 0:
        return None
    i = 12
    for _ in range(qd):
        i = _skip_name(reply, i) + 4
    best = None
    for _ in range(an):
        i = _skip_name(reply, i)
        rtype, _cls, _ttl, rdlen = struct.unpack(">HHIH", reply[i:i + 10])
        i += 10
        if rtype == 33:
            priority, weight, port = struct.unpack(">HHH", reply[i:i + 6])
            target = _read_name(reply, i + 6)
            if best is None or priority < best[0]:
                best = (priority, target, port)
        i += rdlen
    return (best[1], best[2]) if best else None


# ---------------------------------------------------------------- Server List Ping

def _varint(value):
    out = b""
    value &= 0xFFFFFFFF
    while True:
        byte = value & 0x7F
        value >>= 7
        out += bytes([byte | (0x80 if value else 0)])
        if not value:
            return out


def _read_varint(sock):
    value = 0
    for shift in range(0, 35, 7):
        byte = sock.recv(1)
        if not byte:
            raise ConnectionError("closed")
        value |= (byte[0] & 0x7F) << shift
        if not byte[0] & 0x80:
            return value
    raise ValueError("varint too long")


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("closed")
        data += chunk
    return data


def _packet(packet_id, payload=b""):
    body = _varint(packet_id) + payload
    return _varint(len(body)) + body


def ping(host, port=25565, timeout=TIMEOUT):
    """The server's status JSON plus 'latency' (ms). Raises OSError / ValueError."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        h = host.encode("utf-8")
        handshake = _varint(767) + _varint(len(h)) + h + struct.pack(">H", port) + _varint(1)
        sock.sendall(_packet(0, handshake) + _packet(0))
        _read_varint(sock)                                   # packet length
        if _read_varint(sock) != 0:
            raise ValueError("unexpected reply")
        text = _recv_exact(sock, _read_varint(sock)).decode("utf-8", "replace")
        status = json.loads(text)
        start = time.monotonic()
        sock.sendall(_packet(1, struct.pack(">q", int(time.time() * 1000))))
        try:
            _read_varint(sock)
            _read_varint(sock)
            _recv_exact(sock, 8)
            status["latency"] = round((time.monotonic() - start) * 1000)
        except (OSError, ValueError):
            status["latency"] = None
    return status


def resolve(address):
    """'play.example.net', 'host:25566' -> (host, port), following SRV like the game."""
    address = address.strip()
    m = re.fullmatch(r"(.+?)(?::(\d+))?", address)
    host, port = m.group(1), m.group(2)
    if port:
        return host, int(port)
    srv = None if re.fullmatch(r"[\d.]+", host) else srv_lookup(host)
    return srv if srv else (host, 25565)


def motd_text(description):
    """The MOTD as plain text (it can be a string or chat JSON, with § color codes)."""
    def flatten(part):
        if isinstance(part, str):
            return part
        if isinstance(part, dict):
            return flatten(part.get("text", "")) + "".join(flatten(x) for x in part.get("extra", []))
        if isinstance(part, list):
            return "".join(flatten(x) for x in part)
        return ""
    return re.sub(r"§.", "", flatten(description)).strip()


def check(address):
    """{'online', 'players', 'max', 'names', 'version', 'motd', 'latency', 'address'}."""
    host, port = resolve(address)
    try:
        status = ping(host, port)
    except (OSError, ValueError, ConnectionError):
        return {"online": False, "address": address}
    players = status.get("players") or {}
    names = sorted({p.get("name", "") for p in players.get("sample") or [] if p.get("name")
                    and not p.get("name", "").startswith("§")})
    return {"online": True, "address": address, "players": players.get("online", 0),
            "max": players.get("max", 0), "names": names,
            "version": (status.get("version") or {}).get("name", ""),
            "motd": motd_text(status.get("description", "")), "latency": status.get("latency")}


# ---------------------------------------------------------------- joins + bar

def joins(previous, current):
    """Names that appeared since last time (only when both checks saw the server)."""
    if not previous or not previous.get("online") or not current.get("online"):
        return []
    return sorted(set(current.get("names", [])) - set(previous.get("names", [])))


def waybar(info, name):
    if not info:
        return {"text": ""}
    if not info["online"]:
        return {"text": "󰍳 off", "class": "offline", "tooltip": f"{name} is offline (or unreachable)"}
    tip = [f"{name}  ·  {info['players']} / {info['max']} online"]
    if info.get("names"):
        tip.append(", ".join(info["names"]))
    if info.get("latency") is not None:
        tip.append(f"Ping {info['latency']} ms")
    if info.get("version"):
        tip.append(f"Version {info['version']}")
    if info.get("motd"):
        tip.append(info["motd"])
    tip.append("")
    tip.append("Click: open Prism Launcher · Lennox Settings > Game center")
    return {"text": f"󰍳 {info['players']}", "class": "online" if info["players"] else "empty",
            "tooltip": "\n".join(tip)}


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_state(info):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(info, f)
    os.replace(STATE + ".tmp", STATE)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    settings = S.load()
    address = argv[2] if len(argv) > 2 else settings["games"]["mc_server"]
    if not address:
        print(json.dumps({"text": ""}) if mode == "waybar" else "No server set (Lennox Settings > Game center)")
        return 0
    info = check(address)
    name = address.split(".")[-2].capitalize() if address.count(".") >= 1 else address
    if mode == "waybar":
        previous = _load_state()
        if previous and previous.get("address") == address and settings["games"]["mc_joins"]:
            for player in joins(previous, info):
                subprocess.run(["notify-send", "-a", "Lennox", "-i", "applications-games", f"{player} joined {name}",
                                f"{info['players']} online now"], check=False)
        _save_state(info)
        print(json.dumps(waybar(info, name), ensure_ascii=False))
    else:
        print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
