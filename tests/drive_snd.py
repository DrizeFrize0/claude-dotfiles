import os, sys, subprocess
HOME = os.environ["HOME"]; sys.path.insert(0, os.path.join(HOME, ".local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from lennox.app import main as M
errors = []
sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
def shot(n): subprocess.run(["import", "-window", "root", os.environ["SHOTS"] + f"/{n}.png"])
class D(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl); w = self.window
        pg = lambda: w.pages["sound"]
        def scroll(frac):
            adj = pg().widget.get_first_child().get_vadjustment(); adj.set_value(adj.get_lower() + (adj.get_upper() - adj.get_page_size()) * frac)
        steps = [lambda: w.show_page("sound"), lambda: None,
                 lambda: print("mic slider max:", pg().input.volume_row.scale.get_adjustment().get_upper(),
                               "| clean switch:", pg().clean_row.get_active(), "| driver rows:", len(pg().driver_rows)),
                 lambda: scroll(0.45), lambda: shot("sound-1"), lambda: scroll(1.0), lambda: shot("sound-2"),
                 lambda: pg()._fix(), lambda: None, lambda: None,
                 lambda: pg().clean_row.set_active(True), lambda: None, lambda: None,
                 lambda: print("clean switch after toggle:", pg().clean_row.get_active(), "| sensitive:", pg().clean_row.get_sensitive()),
                 lambda: pg()._report(), lambda: None, lambda: shot("sound-3"),
                 lambda: self.quit()]
        st = {"i": 0}
        def step():
            steps[st["i"]](); st["i"] += 1; return st["i"] < len(steps)
        GLib.timeout_add(900, step); return r
D().run(["lennox-settings"])
print("ERRORS:", len(errors), errors[:3])
