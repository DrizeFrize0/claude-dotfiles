"""Self-heal. Run: python3 tests/test_heal.py"""
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_STATE_HOME=os.path.join(T, "state"), XDG_CONFIG_HOME=os.path.join(T, "cfg"),
                  XDG_RUNTIME_DIR=os.path.join(T, "run"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import heal as H  # noqa: E402

fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    c or fails.append(what)


def ctx(**kw):
    base = {"resolve": lambda n: {"142.250.1.1"}, "procs": lambda: {"waybar", "swaync", "awww-daemon"},
            "disk_used": lambda: 40, "exists": lambda p: False,
            "run": lambda argv, t=5: (0, "", ""), "settings": lambda: {"bar": {"enabled": True}},
            "have": lambda c: c in ("swaync", "awww-daemon"), "dns_file": "/nonexistent/dns.conf"}
    base.update(kw)
    return base


check(H.find_problems(ctx()) == [], "a healthy laptop has no problems")

blocked = ctx(resolve=lambda n: {"::"} if "netflix" in n else {"1.2.3.4"})
p = H.find_problems(blocked)
check(len(p) == 1 and p[0]["key"] == "dns" and "www.netflix.com" in p[0]["title"], "a fake answer is found by name")
check(p[0]["fix"][-2:] == ["lennox-securedns", "on"][-2:] or p[0]["fix"][-1] == "on", "the fix is encrypted DNS")
p = H.find_problems(ctx(resolve=lambda n: {"0.0.0.0"}, exists=lambda f: f.endswith("dns.conf")))
check(p[0]["fix"] is None and "still" in p[0]["title"], "encrypted DNS already on: no blind fix, only a pointer")

p = H.find_problems(ctx(exists=lambda f: f == H.PACMAN_LOCK))
check([x["key"] for x in p] == ["pacman-lock"], "a stale package lock is found")
p = H.find_problems(ctx(exists=lambda f: f == H.PACMAN_LOCK, procs=lambda: {"pacman", "waybar", "swaync", "awww-daemon"}))
check(p == [], "but not while pacman is really running")

p = H.find_problems(ctx(disk_used=lambda: 93))
check(p[0]["key"] == "disk-full" and "93%" in p[0]["title"], "a nearly full disk is found")

p = H.find_problems(ctx(procs=lambda: set()))
check({x["key"] for x in p} == {"bar", "notifications", "wallpaper"}, "stopped desktop pieces are found")
p = H.find_problems(ctx(procs=lambda: {"swaync", "awww-daemon"}, settings=lambda: {"bar": {"enabled": False}}))
check(p == [], "a bar you switched off is not a problem")

p = H.find_problems(ctx(run=lambda argv, t=5: (0, "foo.service loaded failed\nbar.service loaded failed\n", "")
                        if "--failed" in argv else (0, "", "")))
check(p and p[0]["key"] == "failed-units" and p[0]["fix"] is None, "failed services are reported, not touched")

# fix_all runs only fixes, then checks again
state = {"disk": 95}
ran = []
c = ctx(disk_used=lambda: state["disk"])


def runner(argv):
    ran.append(argv)
    state["disk"] = 50
    return 0


fixed, left = H.fix_all(c, runner, say=lambda *_: None)
check(fixed == 1 and ran and ran[0][-1] == "now" and left == [], "fix runs the fix and checks again")

# the watcher: two blocked rounds in a row -> one notification, then quiet for six hours
B = 10_000_000
sent = []
notify = lambda kind, title, body: sent.append(kind)  # noqa: E731
s = H.watch_step({}, B, blocked, notify)
check(sent == [], "one blocked round alone is not enough (networks hiccup)")
s = H.watch_step(s, B + 90, blocked, notify)
check(sent == ["dns"], "the second round asks")
s = H.watch_step(s, B + 180, blocked, notify)
check(sent == ["dns"], "and then stays quiet")
s = H.watch_step(s, B + 180 + H.COOLDOWN + 1, blocked, notify)
check(sent == ["dns", "dns"], "until the cooldown is over")
s = H.watch_step(s, B + 99999, ctx(), notify)
check(s["dns_streak"] == 0, "a healthy round resets the count")
sent.clear()
H.watch_step({}, B, ctx(disk_used=lambda: 97), notify)
check(sent == ["disk"], "a disk at 97% asks at once")
H.save_state({"a": 1})
check(H.load_state() == {"a": 1}, "state round-trips")
print("OK heal" if not fails else "FAILED heal: %d" % len(fails))
sys.exit(1 if fails else 0)
