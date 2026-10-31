import os, sys, json, time
sys.path.insert(0, os.path.join(os.environ["HOME"], ".local/share/lennox/python"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from lennox.app import main as M
from lennox import settings as S
fails = []
def check(c, w):
    print(("ok   " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)
class Driver(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl)
        def go():
            self.window.show_page("appearance")
            sw = self.window.pages.get("appearance")
            sw = sw if hasattr(sw, "swatches") else None
            check(sw is not None, "appearance page has swatches")
            if sw:
                check(sw.swatches["wallpaper"].has_css_class("selected"), "wallpaper selected at start")
                sw.swatches["sakura"].emit("clicked")
                def after():
                    check(S.load()["appearance"]["theme"] == "sakura", "click saved theme=sakura")
                    check(sw.swatches["sakura"].has_css_class("selected") and not sw.swatches["wallpaper"].has_css_class("selected"), "ring moved to sakura")
                    check(sw.theme_name.get_label() == "Sakura", "name label shows Sakura")
                    sw.ctx.store.set("appearance.theme", "ocean")
                    check(sw.swatches["ocean"].has_css_class("selected"), "external change (store) updates the ring")
                    self.quit(); return False
                GLib.timeout_add(600, after)
            else:
                self.quit()
            return False
        GLib.timeout_add(1200, go)
        return r
Driver().run(["lennox-settings"])
print("FAILURES:", len(fails), flush=True)
os._exit(1 if fails else 0)
