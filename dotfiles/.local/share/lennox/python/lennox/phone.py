"""Phone link (KDE Connect): your phone's battery, notifications, files, find it.

    python3 -m lennox.phone status                 phones as JSON
    python3 -m lennox.phone pair|unpair|ring|ping ID
    python3 -m lennox.phone send ID FILE...         send files to the phone
    python3 -m lennox.phone clipboard ID            send what you copied

Install the KDE Connect app on the phone (Android: Play Store / F-Droid,
iPhone: App Store) and be on the same Wi-Fi. Phone notifications then show
up on the desktop, and the phone can send files and use the PC as a remote.
"""

import json
import re
import shutil
import subprocess
import sys

CLI = "kdeconnect-cli"


def _run(argv, timeout=10, data=None):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False, input=data)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def parse_devices(text):
    """`kdeconnect-cli -l` -> [{'id', 'name', 'paired', 'reachable'}]."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^- (.+): (\S+) \(([^)]*)\)\s*$", line.strip())
        if not m:
            continue
        state = m.group(3)
        out.append({"name": m.group(1), "id": m.group(2), "paired": "paired" in state and "not paired" not in state,
                    "reachable": "reachable" in state and "not reachable" not in state})
    return out


def _property(device, plugin, interface, name):
    code, out, _ = _run(["gdbus", "call", "--session", "--dest", "org.kde.kdeconnect",
                         "--object-path", f"/modules/kdeconnect/devices/{device}/{plugin}",
                         "--method", "org.freedesktop.DBus.Properties.Get", interface, name], timeout=3)
    return out.strip() if code == 0 else None


def parse_variant(text):
    """gdbus '(<85>,)' / '(<true>,)' -> 85 / True; None if it can't tell."""
    m = re.match(r"^\(<(.*)>,\)$", (text or "").strip())
    if not m:
        return None
    value = m.group(1).strip()
    if value in ("true", "false"):
        return value == "true"
    try:
        return int(value.split()[-1])           # also 'int32 85'
    except ValueError:
        return None


def battery(device):
    charge = parse_variant(_property(device, "battery", "org.kde.kdeconnect.device.battery", "charge"))
    charging = parse_variant(_property(device, "battery", "org.kde.kdeconnect.device.battery", "isCharging"))
    if not isinstance(charge, int) or isinstance(charge, bool) or charge < 0:
        return None, None
    return charge, bool(charging)


def status():
    if not shutil.which(CLI):
        return {"installed": False, "devices": []}
    _run([CLI, "--refresh"], timeout=5)
    code, out, err = _run([CLI, "-l"])
    devices = parse_devices(out) if code == 0 else []
    for d in devices:
        d["battery"], d["charging"] = battery(d["id"]) if d["paired"] and d["reachable"] else (None, None)
    return {"installed": True, "devices": devices, "error": "" if code == 0 else err.strip()}


ACTIONS = {"pair": ["--pair"], "unpair": ["--unpair"], "ring": ["--ring"],
           "ping": ["--ping-msg", "Hi from your PC (Lennox)"]}


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    if mode == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    if not shutil.which(CLI):
        print("KDE Connect is not installed (lennox upgrade)", file=sys.stderr)
        return 1
    if len(argv) < 3:
        print("usage: lennox-phone status | pair|unpair|ring|ping ID | send ID FILE... | clipboard ID",
              file=sys.stderr)
        return 2
    device = argv[2]
    if mode in ACTIONS:
        code, out, err = _run([CLI, "-d", device, *ACTIONS[mode]])
    elif mode == "send" and len(argv) > 3:
        code = 0
        for path in argv[3:]:
            c, out, err = _run([CLI, "-d", device, "--share", path], timeout=30)
            code = code or c
    elif mode == "clipboard":
        _, text, _ = _run(["wl-paste", "--no-newline"])
        if not text:
            print("Nothing copied", file=sys.stderr)
            return 1
        code, out, err = _run([CLI, "-d", device, "--share-text", text])
    else:
        print(f"lennox-phone: unknown command {mode}", file=sys.stderr)
        return 2
    if code != 0:
        print((err or out).strip() or "KDE Connect didn't answer", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
