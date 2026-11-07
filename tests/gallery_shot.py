"""Render the bar style gallery on its own and screenshot it (tests/gallery.png).
Also checks a click on a card switches the style and moves the outline."""
import os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles/.local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk
from lennox.app.bargallery import Gallery
from lennox.app.pages.bar import STYLES

class Store(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, (str,))}
    def __init__(self):
        super().__init__(); self.v = {"bar.style": "lennox"}
    def get(self, p): return self.v[p]
    def set(self, p, v):
        if self.v.get(p) != v:
            self.v[p] = v; self.emit("changed", p)

Adw.init()
store = Store(); g = Gallery(store, STYLES)
win = Gtk.Window(title="gallery"); win.set_default_size(820, 1000)
win.set_child(Gtk.ScrolledWindow(child=Adw.Clamp(child=g.widget, maximum_size=780))); win.present()
fails = []
def pump(s):
    end = time.time() + s
    while time.time() < end:
        GLib.MainContext.default().iteration(False); time.sleep(0.01)
pump(1.5)
subprocess.run(["import", "-window", "root", "-crop", "820x1000+0+0", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery.png")])
ws = [w for w in g.cards.values()]
g.cards["lennox-aurora"].emit("clicked"); pump(0.2)
ok = store.get("bar.style") == "lennox-aurora" and g.cards["lennox-aurora"].has_css_class("bp-selected") \
    and not g.cards["lennox"].has_css_class("bp-selected")
print(("ok   " if ok else "FAIL ") + "click a card: style switches, outline moves", flush=True); ok or fails.append("click")
widths = {v: c.get_width() for v, c in g.cards.items()}
ok = max(widths.values()) - min(widths.values()) <= 1 and len(g.cards) == len(STYLES)
print(("ok   " if ok else "FAIL ") + f"one card per style, same size {set(widths.values())}", flush=True); ok or fails.append("cards")
print("FAILURES:", len(fails), fails, flush=True)
