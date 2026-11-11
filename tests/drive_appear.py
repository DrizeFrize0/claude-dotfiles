import os, sys, subprocess
HOME = os.environ["HOME"]; sys.path.insert(0, os.path.join(HOME, ".local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib, Adw, Gtk
from lennox.app import main as M
def find(w, title):
    if isinstance(w, Adw.PreferencesRow) and w.get_title() == title: return w
    c = w.get_first_child()
    while c:
        r = find(c, title)
        if r: return r
        c = c.get_next_sibling()
class D(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl); w = self.window
        steps = [lambda: w.show_page("appearance"),
                 lambda: (lambda row: (print("row found:", row is not None),
                          w.pages["appearance"].widget.scroll_to_widget(row) if hasattr(w.pages["appearance"].widget, "scroll_to_widget") else row.grab_focus()))(find(w.pages["appearance"].widget, "Window mode")),
                 lambda: subprocess.run(["import", "-window", "root", os.environ["SHOTS"] + "/appearance-windows.png"]),
                 lambda: self.quit()]
        st = {"i": 0}
        def step():
            steps[st["i"]](); st["i"] += 1; return st["i"] < len(steps)
        GLib.timeout_add(1200, step); return r
D().run(["lennox-settings"])
