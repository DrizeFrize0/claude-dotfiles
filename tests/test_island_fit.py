"""The island fits every bar style: reads island.json, takes the skin, moves to a notch
for bottom bars, rebuilds when the bar changes. Run under xvfb:
  xvfb-run -a /usr/bin/python3.12 tests/test_island_fit.py [SHOT_DIR]"""
import json
import os
import subprocess
import sys
import tempfile
import time

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_RUNTIME_DIR=os.path.join(T, "run"), XDG_CONFIG_HOME=os.path.join(T, ".config"),
                  XDG_STATE_HOME=os.path.join(T, "state"), LENNOX_WIDGETS_NO_LAYER="1", GDK_BACKEND="x11",
                  GSK_RENDERER="cairo", NO_AT_BRIDGE="1")
os.makedirs(os.path.join(T, "run", "lennox"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib  # noqa: E402
from lennox import settings as S  # noqa: E402
from lennox.widgets import island as I, main as M  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
FILE = os.path.join(T, "run", "lennox", "island.json")
fails = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        fails.append(what)


def write(**g):
    with open(FILE + ".tmp", "w") as f:
        json.dump(g, f)
    os.replace(FILE + ".tmp", FILE)


def pump(seconds):
    end, ctx = time.time() + seconds, GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False)
        time.sleep(0.01)


def shot(name):
    if SHOTS:
        subprocess.run(["import", "-window", "root", "-crop", "520x90+0+0", os.path.join(SHOTS, f"island-{name}.png")],
                       check=False)


# ---- reading the file
write(style="lennox-material", skin="match", position="top", top=8, height=44)
check(I.island_geometry() == {"position": "top", "top": 8, "height": 44, "skin": "match"}, "reads the fit file")
write(style="x", skin="sparkly", position="top", top=0, height=30)
check(I.island_geometry()["skin"] == "black", "unknown skin falls back to black")
write(style="x", skin="flat", position="top", top=0, height=500)
check(I.island_geometry()["skin"] == "black" and I.island_geometry()["height"] != 500, "silly height ignored")
os.remove(FILE)
check(I.island_geometry()["skin"] == "black", "no file: the bar's own config / defaults")

# ---- the real window
S.set_value("widgets.desktop", False)
S.set_value("widgets.island", True)
S.set_value("widgets.island_place", "bar")
S.set_value("widgets.island_music", False)
write(style="lennox-material", skin="match", position="top", top=8, height=44)
app = M.App()
app.register(None)
app._command([], None)
pump(2)
isl = app.island
check(isl is not None and isl.pill.has_css_class("skin-match"), "the island takes the style's skin")
check(isl.compact_height == 42 and isl.top_margin == 8, f"fits the bar: {isl.compact_height}px at {isl.top_margin}")
check(isl.kind == "clock", f"in the bar it is the clock ({isl.kind})")
shot("match")

for skin in ("black", "glass", "flat", "glow"):
    write(style="s", skin=skin, position="top", top=6, height=36)
    app.refit_island()
    pump(1.2)
    check(app.island is not isl and app.island.pill.has_css_class("skin-" + skin), f"refit to {skin}")
    isl = app.island
    shot(skin)

write(style="lennox-dock", skin="glass", position="bottom", top=0, height=48)
app.refit_island()
pump(1.2)
isl = app.island
check(isl.top_margin == 6 and isl.compact_height == 32, "bottom bar: a notch at the top edge")
check(isl.place == "bar" and isl.kind == "clock", "the notch still shows the clock")

same = isl
app.refit_island()
pump(0.3)
check(app.island is same, "nothing changed: no rebuild")

print("FAILED: %d" % len(fails) if fails else "OK island-fit", flush=True)
sys.exit(1 if fails else 0)
