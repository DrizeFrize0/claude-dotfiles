"""Open Lennox Settings, visit every page, screenshot each, report exceptions."""
import os, sys, subprocess, traceback
HOME = os.environ["HOME"]
OUT = os.environ["SHOTS"]
ONLY = os.environ.get("ONLY", "")
sys.path.insert(0, os.path.join(HOME, ".local/share/lennox/python"))
errors = []
def hook(t, v, tb):
    errors.append("".join(traceback.format_exception(t, v, tb)))
    sys.__excepthook__(t, v, tb)
sys.excepthook = hook

import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from lennox.app import main as M

class Driver(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl)
        pages = [p[0] for p in M.PAGES if not ONLY or p[0] in ONLY.split(",")]
        state = {"i": 0}
        def step():
            i = state["i"]
            if i > 0:
                name = pages[i - 1]
                if isinstance(self.window.pages.get(name), M._ErrorPage):
                    errors.append(f"page {name} failed to build")
                subprocess.run(["import", "-window", "root", os.path.join(OUT, f"{M.PAGE_IDS.index(name):02d}-{name}.png")])
                print("shot", name, flush=True)
            if i >= len(pages):
                self.quit()
                return False
            self.window.show_page(pages[i])
            state["i"] += 1
            return True
        GLib.timeout_add(1200, step)
        return r

Driver().run(["lennox-settings"])
print("ERRORS:", len(errors), flush=True)
for e in errors:
    print(e, flush=True)
