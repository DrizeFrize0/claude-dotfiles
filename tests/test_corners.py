"""Rounded screen corners: each corner window is black in the outer corner and see-through
toward the screen. Run: xvfb-run -a /usr/bin/python3.12 tests/test_corners.py"""
import os
import subprocess
import sys
import tempfile
import time

os.environ.update(LENNOX_WIDGETS_NO_LAYER="1", GDK_BACKEND="x11", GSK_RENDERER="cairo", NO_AT_BRIDGE="1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import corners as C  # noqa: E402

R = 40
fails = []
app = C.Gtk.Application(application_id="dev.lennox.CornersTest")
app.register(None)
C.O.css("window.lennox-overlay { background: #ffffff; }")    # white where the mask is clear, for the test
shot = os.path.join(tempfile.mkdtemp(), "c.txt")
for corner in C.CORNERS:
    win = C.Corner(app, corner, R)
    win.present()
    end, ctx = time.time() + 0.6, C.GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False)
        time.sleep(0.01)
    outer = {"top-left": (1, 1), "top-right": (R - 2, 1), "bottom-left": (1, R - 2), "bottom-right": (R - 2, R - 2)}[corner]
    inner = {"top-left": (R - 3, R - 3), "top-right": (2, R - 3), "bottom-left": (R - 3, 2), "bottom-right": (2, 2)}[corner]
    def pixel(x, y):
        out = subprocess.run(["import", "-window", "root", "-crop", f"1x1+{x}+{y}", "txt:-"], capture_output=True, text=True).stdout
        return out.splitlines()[-1].split()[2] if out.strip() else "?"
    o, i = pixel(*outer), pixel(*inner)
    ok = o.upper().startswith("#000000") and i.upper().startswith("#FFFFFF")
    print(("ok   " if ok else "FAIL ") + f"{corner}: outer {o}, inner {i}", flush=True)
    ok or fails.append(corner)
    win.destroy()
print("OK corners" if not fails else "FAILED corners")
sys.exit(1 if fails else 0)
