import os, sys, subprocess, time
sys.path.insert(0, os.path.expanduser("~/.local/share/lennox/python"))
errors = []
sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from lennox import clockapp as A, clock as C
shot = lambda n: subprocess.run(["import", "-window", "root", os.environ["SHOTS"] + f"/clock-{n}.png"])
class T(A.ClockApp):
    def do_command_line(self, cl):
        r = A.ClockApp.do_command_line(self, cl); w = self.window
        def page(n): w.stack.set_visible_child_name(n)
        steps = [lambda: page("timers"), lambda: shot("timers"),
                 lambda: w._start_timer(300, ""), lambda: (w.timer_custom.set_text("90s Eggs"), w._custom_timer(w.timer_custom)),
                 lambda: print("timers:", [t["label"] for t in C.load()["timers"]]),
                 lambda: page("alarms"), lambda: (w.alarm_time.set_text("6:45am"), w.alarm_label.set_text("Run"), w.alarm_days.set_selected(1), w._add_alarm()),
                 lambda: (w.alarm_time.set_text("nope"), w._add_alarm()),
                 lambda: print("alarms:", [(a["time"], a["days"]) for a in C.load()["alarms"]]), lambda: shot("alarms"),
                 lambda: page("world"), lambda: (w.world_group.get_first_child(), None)[1],
                 lambda: shot("world"),
                 lambda: page("stopwatch"), lambda: w._stopwatch_toggle(), lambda: time.sleep(1.2),
                 lambda: w.change(lambda d, n: C.stopwatch(d, "lap", n)), lambda: shot("stopwatch"),
                 lambda: print("stopwatch:", w.sw_label.get_label(), "laps", len(C.load()["stopwatch"]["laps"])),
                 lambda: page("reminders"), lambda: (w.rem_when.set_text("20m"), w.rem_text.set_text("Stretch"), w._add_reminder()),
                 lambda: print("reminders:", [r["text"] for r in C.load()["reminders"]]), lambda: shot("reminders"),
                 lambda: self.quit()]
        st = {"i": 0}
        def step():
            steps[st["i"]](); st["i"] += 1; return st["i"] < len(steps)
        GLib.timeout_add(500, step); return r
T().run(["lennox-clock"])
print("ERRORS:", len(errors), errors[:3])
