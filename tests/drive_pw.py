import os, sys, subprocess, traceback
HOME = os.environ["HOME"]; OUT = os.environ["SHOTS"]
sys.path.insert(0, os.path.join(HOME, ".local/share/lennox/python"))
errors = []
sys.excepthook = lambda t, v, tb: errors.append("".join(traceback.format_exception(t, v, tb)))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib, Adw
from lennox.app import main as M

def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")])

class D(M.Application):
    def do_command_line(self, cl):
        r = M.Application.do_command_line(self, cl)
        w = self.window
        steps = []
        def page(): return w.pages["passwords"]
        steps.append(lambda: w.show_page("passwords"))
        steps.append(lambda: (print("status:", page().status_row.value_label.get_label()),
                              print("exports:", page().exports_row.get_subtitle(), page().clean_button.get_sensitive()), shot("pw-top")))
        def scroll():
            sw = page().widget.get_first_child()
            adj = sw.get_vadjustment(); adj.set_value(adj.get_upper())
        steps.append(scroll); steps.append(lambda: shot("pw-bottom"))
        steps.append(lambda: page()._connect())  # empty email -> error
        steps.append(lambda: print("email error css:", page().email_row.has_css_class("error")))
        def connect():
            page().email_row.set_text("me@example.com"); page().region_row.set_selected(1); page()._connect()
        steps.append(connect)
        steps.append(lambda: None)
        steps.append(lambda: print("status after connect:", page().status_row.value_label.get_label()))
        steps.append(lambda: page()._confirm_clean())
        steps.append(lambda: shot("pw-dialog"))
        def respond():
            dlg = w.get_visible_dialog(); print("dialog:", dlg.get_heading()); dlg.emit("response", "delete"); dlg.force_close()
        steps.append(respond)
        steps.append(lambda: None)
        steps.append(lambda: print("exports after:", page().exports_row.get_subtitle(), page().clean_button.get_sensitive()))
        state = {"i": 0}
        def step():
            if state["i"] >= len(steps): self.quit(); return False
            steps[state["i"]](); state["i"] += 1; return True
        GLib.timeout_add(1200, step)
        return r
D().run(["lennox-settings"])
print("ERRORS:", len(errors)); [print(e) for e in errors]
