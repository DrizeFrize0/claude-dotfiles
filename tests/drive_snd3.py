import os, sys, subprocess
HOME = os.environ["HOME"]; sys.path.insert(0, os.path.join(HOME, ".local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib, Adw
from lennox.app import main as M
errors = []
sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
toasts = []
class D(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl); w = self.window
        orig = w.toast; w.toast = lambda text, timeout=3: (toasts.append(text), orig(text, timeout))
        pg = lambda: w.pages["sound"]
        def scroll(frac):
            adj = pg().widget.get_first_child().get_vadjustment(); adj.set_value(adj.get_lower() + (adj.get_upper() - adj.get_page_size()) * frac)
        steps = [lambda: w.show_page("sound"), lambda: None,
                 lambda: print("bt switch (on = headset mic):", pg().bt_row.get_active()),
                 lambda: pg().bt_row.set_active(False), lambda: None, lambda: None,
                 lambda: print("bt switch after:", pg().bt_row.get_active()),
                 lambda: scroll(0.3), lambda: subprocess.run(["import", "-window", "root", os.environ["SHOTS"] + "/sound-bt.png"]),
                 lambda: self.quit()]
        st = {"i": 0}
        def step():
            steps[st["i"]](); st["i"] += 1; return st["i"] < len(steps)
        GLib.timeout_add(900, step); return r
D().run(["lennox-settings"])
print("TOASTS:", *toasts, sep="\n  ")
print("ERRORS:", len(errors), errors[:3])
