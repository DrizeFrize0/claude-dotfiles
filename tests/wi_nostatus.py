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


M.StatusWatcher = lambda *a, **k: None
app = M.App()
app.register(None)
app.activate = None
app._command([], None)  # first run: build windows
pump(3)
dash = app.dashboard
check(app.desktop is not None and app.desktop.get_visible(), "desktop widgets shown")
check(not dash.get_visible(), "dashboard hidden at start")

dash.open_dashboard(); pump(3)
check(dash.get_visible(), "dashboard opens")
media = next(c for c in dash.cards if isinstance(c, cards.MediaCard))
check(media.title.get_label() == "Blinding Lights" and media.artist.get_label() == "The Weeknd", "media shows track")
check(media.play.get_icon_name() == "media-playback-pause-symbolic", "playing shows pause button")
check(not media.prev.get_sensitive(), "previous disabled when player says CanGoPrevious=false")
check(media.art_stack.get_visible_child_name() == "art", "cover art shown")
media.play.emit("clicked"); pump(1.5)
check(lines(os.environ["MPRIS_LOG"])[-1:] == ["PlayPause"], "play/pause sent to player")
check(media.play.get_icon_name() == "media-playback-start-symbolic", "paused shows play button")
media.next.emit("clicked"); pump(1.5)
check(media.title.get_label() == "Starboy" and "Daft Punk" in media.artist.get_label(), "next track updates card")

sliders = next(c for c in dash.cards if isinstance(c, cards.SlidersCard))
check(abs(sliders.volume.get_value() - 45) < 0.5 and abs(sliders.brightness.get_value() - 50) < 0.5, "sliders read 45% / 50%")
open(os.environ["STUBLOG"], "w").close()
for v in (60, 65, 70):
    sliders.volume.set_value(v); pump(0.03)
sliders.brightness.set_value(1); pump(0.6)
log = open(os.environ["STUBLOG"]).read()
check(log.count("set-volume") == 1 and "set-volume @DEFAULT_AUDIO_SINK@ 70%" in log, "volume drag sends one command")
check("set 5%" in log, "brightness never set below 5%")
sliders.mute.emit("clicked"); pump(0.6)
check("set-mute @DEFAULT_AUDIO_SINK@ toggle" in open(os.environ["STUBLOG"]).read(), "mute button")

weather = next(c for c in dash.cards if isinstance(c, cards.WeatherCard))
check(weather.temp.get_label() == "8°C" and weather.days.get_visible(), "dashboard weather with forecast days")

notes = next(c for c in dash.cards if isinstance(c, cards.NotesCard))
notes.buffer.set_text("gym 6pm\nserver event saturday"); pump(1.2)
check(data.load_notes() == "gym 6pm\nserver event saturday", "notes autosave")
notes.buffer.set_text("half typed"); dash.close_dashboard(); pump(0.2)
check(data.load_notes() == "half typed", "notes saved when dashboard closes")
data.save_notes("edited elsewhere")
dash.open_dashboard(); pump(1.5)
s, e = notes.buffer.get_bounds()
check(notes.buffer.get_text(s, e, True) == "edited elsewhere", "notes reload outside edits on open")
pump(1.2)
check(data.load_notes() == "edited elsewhere", "reloading notes does not rewrite them")

# Escape closes
ctrl = [c for c in list(dash.observe_controllers()) if isinstance(c, Gtk.EventControllerKey)][0]
ctrl.emit("key-pressed", Gdk.KEY_Escape, 9, 0); pump(0.3)
check(not dash.get_visible(), "Escape closes the dashboard")
check(all(not c.running for c in dash.cards), "cards stop when closed (no background polling)")

# Quick action closes the dashboard and launches the command
dash.open_dashboard(); pump(0.5)
open(os.environ["STUBLOG"], "w").close()
actions = next(c for c in dash.cards if isinstance(c, cards.ActionsCard))
grid = actions.get_last_child()
btn = grid.get_child_at(1, 1)  # Game mode
btn.emit("clicked"); pump(1.0)
check(not dash.get_visible(), "action closes dashboard")
check(os.path.exists(os.path.join(os.environ["XDG_RUNTIME_DIR"], "lennox", "modes", "game")), "action ran lennox-mode game toggle (game mode on)")

# Desktop: media hidden when nothing plays
desk_media = next(c for c in app.desktop.cards if isinstance(c, cards.MediaCard))
check(desk_media.get_visible(), "desktop media visible while a player exists")
os.kill(int(os.environ["FAKE_PID"]), 15); pump(3)
check(not desk_media.get_visible(), "desktop media hides when the player quits")

# Desktop off -> window destroyed, dashboard still works
import json  # noqa: E402
p = os.path.expanduser("~/.config/lennox/settings.json")
d = json.load(open(p)); d["widgets"]["desktop"] = False; json.dump(d, open(p, "w"))
app.reload(); pump(0.5)
check(app.desktop is None, "desktop widgets off")
dash.toggle(); pump(0.5)
check(dash.get_visible(), "dashboard still works with desktop widgets off")
d["widgets"]["desktop"] = True; d["widgets"]["position"] = "bottom-right"; json.dump(d, open(p, "w"))
app.reload(); pump(0.5)
check(app.desktop is not None and app.desktop.get_visible(), "desktop widgets back on")

print("\nFAILURES:", len(fails), fails, flush=True)
os._exit(1 if fails else 0)
