"""Drive the iPhone-style island in-process under xvfb + dbus with fake_mpris."""
import os, subprocess, sys, time
os.environ["LENNOX_WIDGETS_NO_LAYER"] = "1"
sys.path.insert(0, os.path.expanduser("~/.local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gio
from lennox import clock as C, settings as S
from lennox.widgets import main as M, island as I
SP = os.environ["SP"]; fails = []
def check(c, what):
    print(("ok   " if c else "FAIL ") + what, flush=True); c or fails.append(what)
def pump(s):
    end = time.time() + s; ctx = GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False); time.sleep(0.01)
def pump_widths(s):
    """Pump, noting the pill's width every frame: proves it springs, not jumps."""
    seen = []; end = time.time() + s; ctx = GLib.MainContext.default()
    while time.time() < end:
        ctx.iteration(False); time.sleep(0.005); seen.append(isl.pill.get_width())
    return seen
def settled(what):
    """The spring finishes (within 2 s), at exactly the content's size, and stops (no timer left)."""
    end = time.time() + 2
    while isl.pill.moving() and time.time() < end:
        pump(0.05)
    pump(0.05)
    size = (isl.pill.get_width(), isl.pill.get_height())
    check(not isl.pill.moving() and isl.pill.size is None and size == isl.pill.content_size(),
          f"{what}: spring ends at the right size {size} = {isl.pill.content_size()}")
def shot(n):
    subprocess.run(["import", "-window", "root", "-crop", "560x330+0+0", f"{SP}/isl-{n}.png"])
I.SOUNDS = [f"{SP}/alarm.oga"]; open(I.SOUNDS[0], "w").close()
S.set_value("widgets.desktop", False); S.set_value("widgets.island_place", "bar")
from gi.repository import Gtk
app = M.App(); app.register(None)
backdrop = Gtk.Window(title="backdrop"); backdrop.set_default_size(560, 330); backdrop.set_decorated(False)
css = Gtk.CssProvider(); css.load_from_string("window.backdrop { background: #8a8f98; }")
Gtk.StyleContext.add_provider_for_display(backdrop.get_display(), css, 900); backdrop.add_css_class("backdrop")
backdrop.present(); pump(0.5)
app._command([], None)
isl = app.island
pump(5)
check(isl is not None and isl.place == "bar", "island in the bar")
check(all(isinstance(I.island_icon(n), Gio.Icon) for n in ("alarm-symbolic", "timer-symbolic", "audio-x-generic-symbolic",
      "find-location-symbolic", "media-record-symbolic", "audio-volume-high-symbolic", "battery-full-charging-symbolic")),
      "island activities use the bundled icon set")
check(isl.kind == "music" and isl.get_visible(), f"music showing (kind={isl.kind})")
check(isl.label.get_label() == "Blinding Lights", f"compact title: {isl.label.get_label()}")
check(isl.bars.get_visible() and isl.bars.tick is not None, "music bars dancing"); h1=[b.get_size_request()[1] for b in isl.bars.bars]; pump(0.3); h2=[b.get_size_request()[1] for b in isl.bars.bars]; check(h1 != h2, f"bars move {h1} -> {h2}")
shot("music")
check(isl.get_height() == isl.compact_height + 2, f"compact pill = the bar's height ({isl.get_height()})")
seen = pump_widths(1.0)
isl._hover(True); seen = pump_widths(1.2)
check(len(set(seen)) > 4 and max(seen) > seen[-1], f"hover springs open ({len(set(seen))} sizes, peak {max(seen)} -> {seen[-1]})")
settled("open")
check(isl.reveal.get_reveal_child() and isl.pill.has_css_class("expanded"), "hover grows it into the card")
check(isl.progress_row.get_visible() and 0.3 < isl.progress.get_fraction() < 0.5, f"progress {isl.progress.get_fraction():.2f} (1:13 of 3:20)")
shot("music-open")
isl._hover(False); pump(1.0)
check(not isl.reveal.get_reveal_child(), "leaving closes it")
settled("closed"); check(isl.get_height() == isl.compact_height + 2, f"closed: back to the bar's height ({isl.get_height()})")
# nothing happening: the clock
S.set_value("widgets.island_music", False); app.reload(); pump(1.5)
check(isl.kind == "clock" and isl.label.get_label().count(":") == 1, f"idle = clock ({isl.kind}: {isl.label.get_label()})")
shot("clock")
check(not isl.pill.moving() and isl.bars.tick is None, "idle clock: no animation or timer running")
isl._clicked(); pump(0.6)
check(isl.reveal.get_reveal_child(), "click opens the clock card")
shot("clock-open")
isl._clicked(); pump(0.6)
# fullscreen hides it
isl.state["fullscreen"] = True; isl.render(); check(not isl.get_visible(), "hidden in fullscreen"); isl.state["fullscreen"] = False
# a notification over D-Bus
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
for args in (GLib.Variant("(ss)", ("bad", "x")),
             GLib.Variant("(susssasa{sv}i)", ("Discord", 0, "", "Sam: you on?", "", [], {"urgency": GLib.Variant("y", 1)}, 5000))):
    try:
        bus.call_sync("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                      "org.freedesktop.Notifications", "Notify", args, None, Gio.DBusCallFlags.NONE, 500, None)
    except GLib.Error:
        pass
pump(1.5)
check(isl.kind == "event" and "Sam" in isl.label.get_label(), f"notification ({isl.kind}: {isl.label.get_label()})")
settled("notification bounce")
shot("notification")
pump(4.5)
with C.edit() as d: C.add_timer(d, 4, "Pizza", time.time())
pump(1.5)
check(isl.kind == "timer" and isl.label.get_label() == "Pizza", f"timer ({isl.kind} {isl.detail.get_label()})")
shot("timer")
pump(3.5)
check(isl.kind == "ringing" and isl.reveal.get_reveal_child() and app.engine.sound is not None, f"ringing opens with Snooze / Stop ({isl.kind})")
settled("ringing"); shot("ringing")
isl._clock(lambda d, n: C.stop_ringing(d)); pump(1.2)
check(isl.kind == "clock" and app.engine.sound is None, "Stop silences, back to the clock")
from lennox import focus as F
F.save_state({"phase": "focus", "start": time.time(), "end": time.time() + 1500, "minutes": 25}); pump(1.5)
check(isl.kind == "focus" and isl.label.get_label() == "Focus" and isl.detail.get_label().startswith("24:"), f"focus ({isl.kind} {isl.detail.get_label()})")
shot("focus")
isl._clicked(); pump(0.8)
check(isl.reveal.get_reveal_child(), "click opens the focus card")
shot("focus-open")
isl._clicked(); pump(0.4)
F.save_state({"phase": "break", "start": time.time(), "end": time.time() + 300, "minutes": 25}); pump(1.5)
check(isl.kind == "focus" and isl.label.get_label() == "Break", f"break ({isl.label.get_label()})")
F.save_state(None); pump(1.5)
check(isl.kind == "clock", "focus over: back to the clock")
# two at once: music + a timer split into the pill and a linked blob
check(I.choose_two({"music": {"playing": True, "title": "x"}, "next_up": ("timer", {"id": "t"}, 60)}, 0)[1][0] == "music"
      and I.choose_two({"music": {"playing": True}, "event": {"until": 9}}, 0)[1] is None, "choose_two: timer + music blob, events never split")
S.set_value("widgets.island_music", True); app.reload(); pump(2.5)
check(isl.kind == "music" and not isl.blob_reveal.get_reveal_child(), f"music alone: one pill ({isl.kind})")
with C.edit() as d: C.add_timer(d, 600, "Tea", time.time())
pump(1.5)
check(isl.kind == "timer" and isl.blob_kind == "music" and isl.blob_reveal.get_reveal_child(),
      f"music + timer: the pill splits (pill {isl.kind}, blob {isl.blob_kind})")
pump(0.6); settled("split")
check(isl.get_height() == isl.compact_height + 2 and isl.blob.get_height() == isl.pill.get_height(),
      f"split: both blobs the bar's height ({isl.get_height()}, {isl.blob.get_height()})")
shot("split")
isl._blob_clicked(); pump(1.0)
check(isl.kind == "music" and isl.blob_kind == "timer" and isl.blob_label.get_label().startswith("9:"),
      f"click the blob: they swap (pill {isl.kind}, blob {isl.blob_kind} {isl.blob_label.get_label()})")
settled("swap"); shot("split-swap")
isl._hover(True); pump(1.2)
check(isl.reveal.get_reveal_child() and not isl.blob_reveal.get_reveal_child(), "open: one card, no blob")
isl._hover(False); pump(1.2)
with C.edit() as d: C.cancel(d, d["timers"][-1]["id"])
pump(1.5)
check(isl.kind == "music" and not isl.blob_reveal.get_reveal_child() and isl.prefer is None, "timer gone: one pill again")
settled("joined")
S.set_value("widgets.island_music", False); app.reload(); pump(1)
S.set_value("widgets.island_place", "below"); app.reload(); pump(1)
check(app.island is not None and app.island.place == "below" and not app.island.get_visible(), "below the bar: hidden when idle")
S.set_value("widgets.island", False); app.reload(); pump(0.5)
check(app.island is None, "island off")
with C.edit() as d: C.add_timer(d, 1, "Tea", time.time())
pump(2.5)
check(C.load()["ringing"] and app.engine.sound is not None, "timers still ring with the island off")
print("FAILURES:", len(fails), fails, flush=True)
app.quit()
