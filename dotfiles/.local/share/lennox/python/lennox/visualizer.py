"""Music wallpaper: the bottom of the desktop pulses and flows with what's playing, in your theme colors.

    python3 -m lennox.visualizer start|stop|sync|run

Uses `cava` to listen to the sound. It sits behind your windows, lets clicks
through, and hides itself while nothing plays so it costs nothing then.
"""

import os
import subprocess
import sys

from . import overlay as O

Gtk, GLib = O.Gtk, O.GLib
BARS = 56
CONFIG = """[general]
bars = {bars}
framerate = 40
[input]
method = pipewire
source = auto
[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 100
bar_delimiter = 59
frame_delimiter = 10
[smoothing]
noise_reduction = 70
"""


def parse_frame(line, bars=BARS):
    """'12;40;...' -> [0..1] floats (padded or cut to `bars`)."""
    vals = [min(max(int(p), 0), 100) / 100 for p in line.strip().split(";") if p.strip().isdigit()]
    return (vals + [0.0] * bars)[:bars]


class Window(Gtk.Window):
    HEIGHT = 340

    def __init__(self):
        super().__init__(title="Lennox music wallpaper", decorated=False, default_width=1280, default_height=self.HEIGHT)
        self.add_css_class("lennox-overlay")
        O.css(O.TRANSPARENT)
        self.levels = [0.0] * BARS
        self.quiet_since = 0
        self.canvas = O.Canvas(self.draw, self.step, fps=40)
        self.set_child(self.canvas)
        O.configure(self, "lennox-visualizer", "bottom", "none", ("bottom", "left", "right"), -1)
        O.click_through(self)
        self.cava = None
        self._start_cava()

    def _start_cava(self):
        runtime = os.path.join(O.S.RUNTIME_DIR)
        os.makedirs(runtime, exist_ok=True)
        path = os.path.join(runtime, "cava.conf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(CONFIG.format(bars=BARS))
        try:
            self.cava = subprocess.Popen(["cava", "-p", path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError:
            print("cava isn't installed (lennox upgrade installs it)", file=sys.stderr)
            sys.exit(1)
        GLib.io_add_watch(self.cava.stdout.fileno(), GLib.IO_IN | GLib.IO_HUP, self._data)

    def _data(self, _fd, cond):
        if cond & GLib.IO_HUP:
            return False
        line = self.cava.stdout.readline()
        if line:
            self.levels = parse_frame(line)
        return True

    def step(self, dt, _w, _h):
        loud = max(self.levels) > 0.02
        if loud:
            self.quiet_since = 0
            if not self.get_visible():
                self.set_visible(True)
        else:
            self.quiet_since += dt
            if self.quiet_since > 4 and self.get_visible():
                self.set_visible(False)            # nothing is playing: no drawing at all

    def draw(self, snap, w, h):
        r, g, b = O.accent()
        mean = sum(self.levels) / len(self.levels)
        O.fill(snap, 0, h * 0.35, w, h * 0.65, O.rgba(r, g, b, 0.04 + 0.14 * mean))
        slot = w / BARS
        for i, level in enumerate(self.levels):
            bar = max(4.0, level * h * 0.8)
            O.fill(snap, i * slot + slot * 0.18, h - bar, slot * 0.64, bar, O.rgba(r, g, b, 0.22 + 0.4 * level), slot * 0.3)

    def stop(self):
        if self.cava:
            self.cava.terminate()


def run():
    O.claim("visualizer")
    app = Gtk.Application(application_id="dev.lennox.Visualizer")

    def activate(a):
        win = Window()
        win.set_application(a)
        win.present()
        win.canvas.start()
        a.connect("shutdown", lambda *_a: win.stop())
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 15, lambda: a.quit() or False)
    app.connect("activate", activate)
    return app.run([])


def main(argv):
    code = O.serve("visualizer", "visualizer.on", argv, run)
    if code is None:
        print("usage: lennox-visualizer start | stop | sync", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
