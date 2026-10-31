import os, sys
sys.path.insert(0, os.path.join(os.environ["HOME"], ".local/share/lennox/python"))
print("start", flush=True)
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib, Adw
print("imported", flush=True)
from lennox.app import main as M
print("app module", flush=True)
app = M.Application()
def later():
    print("timeout fired; window:", app.window, flush=True)
    app.quit()
    return False
orig = M.Application.do_command_line
def patched(self, cl):
    print("command_line", flush=True)
    r = orig(self, cl)
    print("window built", flush=True)
    GLib.timeout_add(1000, later)
    return r
M.Application.do_command_line = patched
print("run ->", app.run(["x"]), flush=True)
