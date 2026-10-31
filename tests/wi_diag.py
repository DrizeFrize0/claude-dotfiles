"""Drive the widgets in-process: clicks, sliders, keys, notes. Run under xvfb + dbus with fake_mpris."""
import os
import sys
import time

os.environ["LENNOX_WIDGETS_NO_LAYER"] = "1"
sys.path.insert(0, os.path.expanduser("~/.local/share/lennox/python"))
import gi  # noqa: E402
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402
from lennox.widgets import cards, data, main as M  # noqa: E402

fails = []
SP = os.environ["SP"]


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        fails.append(what)


def pump(seconds):
    end = time.time() + seconds
    ctx = GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False)
        time.sleep(0.01)


def lines(path):
    try:
        return open(path).read().split()
    except OSError:
        return []


app = M.App()
app.register(None)
app.activate = None
app._command([], None)  # first run: build windows
pump(3)
dash = app.dashboard
check(app.desktop is not None and app.desktop.get_visible(), "desktop widgets shown")
check(not dash.get_visible(), "dashboard hidden at start")

import time as _t
for _ in range(3):
    t0=_t.time(); np=app.mpris.now_playing(); print("DIAG now_playing:", (np or {}).get("title"), f"{(_t.time()-t0)*1000:.0f} ms", flush=True); pump(1)
import threading, traceback
def worker():
    try:
        r = app.mpris.now_playing(); print("DIAG thread now_playing:", (r or {}).get("title"), flush=True)
    except Exception:
        print("DIAG thread EXC:", traceback.format_exc(), flush=True)
th = threading.Thread(target=worker); th.start(); th.join(5); pump(0.5)
print("DIAG players:", app.mpris.players(), flush=True)
dash.open_dashboard(); pump(3)
media_dbg = next(c for c in dash.cards if isinstance(c, cards.MediaCard))
print("DIAG card title:", repr(media_dbg.title.get_label()), flush=True)
check(dash.get_visible(), "dashboard opens")
media = next(c for c in dash.cards if isinstance(c, cards.MediaCard))
check(media.title.get_label() == "Blinding Lights" and media.artist.get_label() == "The Weeknd", "media shows track")
check(media.play.get_icon_name() == "media-playback-pause-symbolic", "playing shows pause button")
check(not media.prev.get_sensitive(), "previous disabled when player says CanGoPrevious=false")
print("DIAG done", flush=True); app.quit()
