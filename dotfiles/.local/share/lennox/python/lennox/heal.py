"""Self-heal: find what is broken and fix it, or offer the fix.

    python3 -m lennox.heal check [--json]   what is wrong, with the fix for each
    python3 -m lennox.heal fix              apply the fixes (asks for your password when one needs it)
    python3 -m lennox.heal watch            (started at login) tells you when a site is blocked or the disk is full

What it knows: a network that answers "::" for real sites (fix: encrypted DNS), a stuck package lock,
a disk that is nearly full, a bar / notifications / wallpaper that is not running, the NVIDIA driver
missing for the new kernel, the freeze guard being off. Things it can only report (a read-only disk,
failed services) come with the command to look closer. Nothing is deleted except package-manager
leftovers and caches.
"""

import fcntl
import json
import os
import shutil
import socket
import sys
import time

from . import net
from . import settings as S
from . import sh

STATE = os.path.join(S.STATE_DIR, "heal.json")
LOCK = os.path.join(S.RUNTIME_DIR, "heal-watch.lock")
CHECK_NAMES = ["www.google.com", "www.netflix.com", "www.youtube.com", "github.com"]
PACMAN_LOCK = "/var/lib/pacman/db.lck"
PACKAGE_TOOLS = {"pacman", "paru", "yay", "lennox-update", "lennox-autoupdate", "pamac"}
COOLDOWN = 6 * 3600                  # the same warning at most every 6 hours
INTERVAL = 90


def default_ctx():
    def resolve(name):
        try:
            return {i[4][0] for i in socket.getaddrinfo(name, 443, proto=socket.IPPROTO_TCP)}
        except (OSError, UnicodeError):
            return set()

    def procs():
        names = set()
        try:
            for pid in os.listdir("/proc"):
                if pid.isdigit():
                    try:
                        with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                            names.add(f.read().strip())
                    except OSError:
                        pass
        except OSError:
            pass
        return names

    def disk_used():
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        return round(100 * (total - st.f_bavail * st.f_frsize) / total) if total else 0

    return {"resolve": resolve, "procs": procs, "disk_used": disk_used, "exists": os.path.exists,
            "run": sh.run, "settings": S.load, "have": lambda c: shutil.which(c) is not None,
            "dns_file": "/etc/systemd/resolved.conf.d/lennox-dns.conf"}


def problem(key, title, hint, fix=None, root=False):
    return {"key": key, "title": title, "hint": hint, "fix": fix, "root": root}


def check_dns(ctx):
    blocked = [n for n in CHECK_NAMES if net.fake_answer(ctx["resolve"](n))]
    if not blocked:
        return None
    if ctx["exists"](ctx["dns_file"]):
        return problem("dns", f"Encrypted DNS is on but {blocked[0]} still gets a fake answer",
                       "Run: lennox-net check, and send the output to Claude")
    return problem("dns", f"This network blocks {', '.join(blocked)} (its DNS answers with a fake address)",
                   "Encrypted DNS fixes it: lennox-securedns on", [sh.bin_path("lennox-securedns"), "on"], True)


def check_pacman_lock(ctx):
    if not ctx["exists"](PACMAN_LOCK) or ctx["procs"]() & PACKAGE_TOOLS:
        return None
    return problem("pacman-lock", "A package lock is left over from a stopped update",
                   "Safe to remove while no update is running", ["sudo", "rm", "-f", PACMAN_LOCK], True)


def check_disk(ctx):
    used = ctx["disk_used"]()
    if used < 90:
        return None
    return problem("disk-full", f"The disk is {used}% full",
                   "Clean old package downloads, logs, caches: lennox-cleanup now",
                   [sh.bin_path("lennox-cleanup"), "now"], True)


def check_desktop(ctx):
    running = ctx["procs"]()
    settings = ctx["settings"]()
    out = []
    if S.get(settings, "bar.enabled") and "waybar" not in running:
        out.append(problem("bar", "The bar is not running", "Restart it: lennox-bar start", [sh.bin_path("lennox-bar"), "start"]))
    if "swaync" not in running and ctx["have"]("swaync"):
        out.append(problem("notifications", "Notifications are not running", "Start them again", ["setsid", "-f", "swaync"]))
    if "awww-daemon" not in running and ctx["have"]("awww-daemon"):
        out.append(problem("wallpaper", "The wallpaper service is not running", "Start it again", ["setsid", "-f", "awww-daemon"]))
    return out


def check_driver(ctx):
    if not ctx["have"]("lennox-gpu") and not os.path.exists(sh.bin_path("lennox-gpu")):
        return None
    code, out, _err = ctx["run"]([sh.bin_path("lennox-gpu"), "check-driver"], 20)
    if code == 0:
        return None
    return problem("nvidia", "The NVIDIA driver is not built for every installed kernel",
                   "Rebuild it: sudo dkms autoinstall (then restart)", ["sudo", "dkms", "autoinstall"], True)


def check_oom(ctx):
    if not ctx["have"]("earlyoom"):
        return None
    code, _out, _err = ctx["run"](["systemctl", "is-active", "--quiet", "earlyoom"], 5)
    if code == 0:
        return None
    return problem("earlyoom", "The freeze guard (earlyoom) is off", "Turn it on again",
                   ["sudo", "systemctl", "enable", "--now", "earlyoom"], True)


def check_report_only(ctx):
    out = []
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                p = line.split()
                if len(p) > 3 and p[1] == "/" and "ro" in p[3].split(","):
                    out.append(problem("readonly", "The disk is READ-ONLY (btrfs protected it after finding damage)",
                                       "Look closer: lennox-disk check"))
    except OSError:
        pass
    code, listing, _err = ctx["run"](["systemctl", "--failed", "--no-legend", "--plain"], 5)
    failed = [ln.split()[0] for ln in listing.splitlines() if ln.strip()] if code == 0 else []
    if failed:
        out.append(problem("failed-units", f"{len(failed)} service(s) failed: {', '.join(failed[:3])}",
                           "Look closer: systemctl --failed   (reset with: sudo systemctl reset-failed)"))
    return out


CHECKS = [check_dns, check_pacman_lock, check_disk, check_desktop, check_driver, check_oom, check_report_only]


def find_problems(ctx=None):
    ctx = ctx or default_ctx()
    found = []
    for fn in CHECKS:
        got = fn(ctx)
        if isinstance(got, list):
            found += got
        elif got:
            found.append(got)
    return found


def apply(p, runner=None):
    """Run one problem's fix with the terminal attached (sudo may ask for a password). True when it worked."""
    import subprocess
    if not p["fix"]:
        return False
    runner = runner or (lambda argv: subprocess.run(argv, check=False).returncode)
    return runner(p["fix"]) == 0


def fix_all(ctx=None, runner=None, say=print):
    """Apply every fix there is, then check again. Returns (fixed, left)."""
    ctx = ctx or default_ctx()
    before = find_problems(ctx)
    fixed = 0
    for p in before:
        if not p["fix"]:
            continue
        say(f":: {p['title']}")
        if apply(p, runner):
            fixed += 1
    left = find_problems(ctx)
    return fixed, left


# ------------------------------------------------------------------ the watcher

def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(data):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(STATE + ".tmp", STATE)


def watch_step(state, now, ctx, notify):
    """One round of the watcher: DNS blocked twice in a row, or the disk almost full -> one notification
    (not more often than the cooldown). Returns the new state."""
    state = dict(state)
    quiet = state.setdefault("last", {})
    blocked = check_dns(ctx)
    state["dns_streak"] = (state.get("dns_streak", 0) + 1) if blocked and blocked["fix"] else 0
    if state["dns_streak"] >= 2 and now - quiet.get("dns", 0) > COOLDOWN:
        quiet["dns"] = now
        notify("dns", "A site is blocked on this network", blocked["title"].split(" (")[0] + ". Fix it with encrypted DNS?")
    if ctx["disk_used"]() >= 95 and now - quiet.get("disk", 0) > COOLDOWN:
        quiet["disk"] = now
        notify("disk", "The disk is almost full", "Clean old downloads, logs and caches?")
    return state


def notify_action(kind, title, body):
    """Shows the notification; clicking the button runs the fix in a terminal."""
    import subprocess
    cmd = {"dns": "lennox-securedns on", "disk": "lennox-cleanup now"}[kind]
    try:
        choice = subprocess.run(["notify-send", "-a", "Lennox", "-i", "dialog-warning", "-t", "30000",
                                 "-A", "fix=Fix it now", title, body],
                                capture_output=True, text=True, timeout=60, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return
    if choice == "fix":
        subprocess.Popen(["setsid", "-f", "kitty", "--hold", "--class", "lennox-floating", "--title", "Lennox fix",
                          "sh", "-c", f"PATH=$HOME/.local/bin:$PATH {cmd}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    ctx = default_ctx()
    state = load_state()
    while True:
        try:
            if S.get(S.load(), "safety.heal"):
                state = watch_step(state, time.time(), ctx, notify_action)
                save_state(state)
        except Exception as e:               # the watcher must never die over one odd round
            print(f"lennox-heal: {e}", file=sys.stderr)
        time.sleep(INTERVAL)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        found = find_problems()
        if "--json" in argv:
            print(json.dumps([{k: v for k, v in p.items() if k != "fix"} | {"fixable": bool(p["fix"])} for p in found]))
            return 1 if found else 0
        if not found:
            print("Nothing is wrong.")
            return 0
        for p in found:
            print(f"  ✗ {p['title']}\n      {p['hint']}" + ("   [lennox-heal fix]" if p["fix"] else ""))
        return 1
    if cmd == "fix":
        fixed, left = fix_all()
        print(f"Fixed {fixed}." if fixed else "Nothing to fix.")
        for p in left:
            print(f"  still: {p['title']}\n      {p['hint']}")
        return 1 if left else 0
    if cmd == "watch":
        return watch()
    print("usage: lennox-heal check [--json] | fix | watch", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
