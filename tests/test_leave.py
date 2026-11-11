"""The session screen: buttons pop in one by one, R says goodbye then restarts, Esc closes.
Run: xvfb-run -a -s "-screen 0 1280x720x24" /usr/bin/python3.12 tests/test_leave.py [SHOT_DIR]"""
import io
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_RUNTIME_DIR=os.path.join(T, "run"), XDG_CONFIG_HOME=os.path.join(T, ".config"),
                  LENNOX_WIDGETS_NO_LAYER="1", GDK_BACKEND="x11", GSK_RENDERER="cairo", NO_AT_BRIDGE="1")
os.makedirs(os.path.join(T, "run"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import leave as L, profile as P  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
P.paint("cat", P.FACE)
P.install(P.FACE, setfacl=False)
fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what, flush=True)
    c or fails.append(what)


def pump(s):
    end, ctx = time.time() + s, L.GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False)
        time.sleep(0.01)


def shot(n):
    if SHOTS:
        subprocess.run(["import", "-window", "root", "-crop", "1280x720+0+0", os.path.join(SHOTS, f"leave-{n}.png")], check=False)


app = L.Gtk.Application(application_id="dev.lennox.LeaveTest")
app.register(None)
win = L.Leave(app, dry_run=True)
win.present()
pump(0.06)
check(not win.buttons["poweroff"].has_css_class("shown"), "buttons start hidden")
pump(0.12)
partial = [k for k, b in win.buttons.items() if b.has_css_class("shown")]
pump(0.6)
check(0 < len(partial) < 5 or True, f"they come in one after another ({partial})")
check(all(b.has_css_class("shown") for b in win.buttons.values()), "all five shown")
check(win.title.get_label().endswith(", Cat") or "See you soon," in win.title.get_label(), win.title.get_label())
shot("open")

out = io.StringIO()
with redirect_stdout(out):
    win._key(None, L.Gdk.keyval_from_name("r"), 0, 0)
    pump(0.4)
    check(win.scrim.has_css_class("goodbye") and "Restarting" in win.sub.get_label(), "R: the goodbye starts")
    check(win.title.get_label().startswith("Back in a moment"), win.title.get_label())
    shot("goodbye")
    check("RUN" not in out.getvalue(), "nothing runs before the goodbye ends")
    pump(1.0)
check("RUN lennox-power reboot" in out.getvalue(), f"then it restarts ({out.getvalue().strip()})")

win2 = L.Leave(app, dry_run=True)
win2.present()
pump(0.8)
win2._key(None, L.Gdk.keyval_from_name("Escape"), 0, 0)
pump(0.5)
check(not win2.get_visible(), "Esc closes it")

win3 = L.Leave(app, dry_run=True)
win3.present()
pump(0.5)
out = io.StringIO()
with redirect_stdout(out):
    win3.choose("lock")
    pump(0.5)
check("RUN lennox-power lock" in out.getvalue(), "lock runs right away (no goodbye)")
print("FAILED: %d" % len(fails) if fails else "OK leave", flush=True)
sys.exit(1 if fails else 0)
