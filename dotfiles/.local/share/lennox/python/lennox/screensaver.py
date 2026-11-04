"""Screensaver: a calm animation after a few idle minutes, before the lock screen.

    python3 -m lennox.screensaver [stars|rain|aurora] [--seconds N]

Any key, click or movement closes it. Lennox Settings > Extras turns it on and
picks the style (hypridle starts it).
"""

import math
import random
import signal
import subprocess
import sys
import time

from . import overlay as O

Gtk, GLib, Gdk = O.Gtk, O.GLib, O.Gdk


class Stars:
    """Slow twinkling stars drifting sideways."""

    def __init__(self, n=140, rng=random):
        self.rng = rng
        self.stars = [[rng.random(), rng.random(), rng.uniform(0.4, 1.6), rng.uniform(0, 6.3), rng.uniform(0.01, 0.04)] for _ in range(n)]
        self.t = 0.0

    def step(self, dt):
        self.t += dt
        for s in self.stars:
            s[0] = (s[0] + s[4] * dt) % 1.0

    def draw(self, snap, w, h):
        O.fill(snap, 0, 0, w, h, O.rgba(0.01, 0.015, 0.05))
        r, g, b = O.accent()
        for x, y, size, phase, _v in self.stars:
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self.t * 1.3 + phase))
            side = size * 2
            O.fill(snap, x * w, y * h, side, side, O.rgba(0.85 + 0.15 * r, 0.9 + 0.1 * g, 1.0, a))     # a square: no clip node per star


class Rain:
    """Drops running down dark glass, each leaving a thin trail."""

    def __init__(self, n=45, rng=random):
        self.rng = rng
        self.drops = [self._new(True) for _ in range(n)]

    def _new(self, anywhere=False):
        r = self.rng
        return [r.random(), r.random() if anywhere else -0.05, r.uniform(0.08, 0.3), r.uniform(1.5, 4.0), r.uniform(0.05, 0.2)]

    def step(self, dt):
        for i, d in enumerate(self.drops):
            d[1] += d[2] * dt
            if d[1] > 1.1:
                self.drops[i] = self._new()

    def draw(self, snap, w, h):
        O.fill(snap, 0, 0, w, h, O.rgba(0.02, 0.03, 0.06))
        r, g, b = O.accent()
        for x, y, v, size, trail in self.drops:
            O.fill(snap, x * w - size / 4, (y - trail) * h, size / 2, trail * h, O.rgba(r, g, b, 0.10))
            O.fill(snap, x * w - size / 2, y * h, size, size * 1.6, O.rgba(0.8 + 0.2 * r, 0.9, 1.0, 0.55))


class Aurora:
    """Soft green and violet curtains swaying."""

    def __init__(self):
        self.t = 0.0

    def step(self, dt):
        self.t += dt

    def draw(self, snap, w, h):
        O.fill(snap, 0, 0, w, h, O.rgba(0.01, 0.02, 0.05))
        colors = [(0.2, 1.0, 0.6), (0.5, 0.4, 1.0), (0.2, 0.8, 1.0)]
        n = 26
        for i, (r, g, b) in enumerate(colors):
            for k in range(n):
                x = (k + 0.5) / n * w + math.sin(self.t * 0.4 + k * 0.17 + i * 2) * 50
                top = h * (0.10 + 0.12 * i) + math.sin(self.t * 0.6 + k * 0.23 + i) * 45
                height = h * 0.5 + math.sin(self.t * 0.3 + k * 0.1) * 60
                rect = O.Graphene.Rect().init(x - w / n, top, 2.4 * w / n, height)
                snap.append_linear_gradient(rect, O.Graphene.Point().init(x, top), O.Graphene.Point().init(x, top + height),
                                            [O.cstop(0.0, O.rgba(r, g, b, 0.0)), O.cstop(0.35, O.rgba(r, g, b, 0.16)),
                                             O.cstop(1.0, O.rgba(r, g, b, 0.0))])


STYLES = {"stars": Stars, "rain": Rain, "aurora": Aurora}
FPS = {"stars": 15, "rain": 20, "aurora": 12}      # calm scenes do not need 60: this keeps the processor nearly idle
MAX_MINUTES = 12                                    # it never stays on longer than this, whatever happens


class Window(Gtk.Window):
    def __init__(self, style, seconds=0):
        super().__init__(title="Lennox screensaver", decorated=False)
        self.add_css_class("lennox-overlay")
        O.css(O.TRANSPARENT)
        self.scene = STYLES.get(style, Stars)()
        self.style = style
        self.canvas = O.Canvas(self.scene.draw, lambda dt, _w, _h: self.scene.step(dt), fps=FPS[style if style in FPS else "stars"])
        self.set_child(self.canvas)
        if not O.configure(self, "lennox-screensaver", "overlay", "exclusive"):
            self.set_default_size(960, 600)
        else:
            self.set_cursor_from_name("none")
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda *_a: self.close() or True)
        self.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_a: self.close())
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        self.armed_at, self.last = time.monotonic() + 0.8, None
        motion.connect("motion", self._moved)
        self.add_controller(motion)
        self.canvas.start()
        GLib.timeout_add_seconds(seconds or MAX_MINUTES * 60, lambda: self.close() or False)
        GLib.timeout_add_seconds(3, self._locked_check)

    def _locked_check(self):
        """The lock screen took over (or the session ended): there is nobody to show this to."""
        if subprocess.run(["pidof", "hyprlock"], capture_output=True, check=False).returncode == 0:
            self.close()
            return False
        return True

    def _moved(self, _c, x, y):
        if time.monotonic() < self.armed_at:
            self.last = (x, y)
            return
        if self.last is None:
            self.last = (x, y)
        elif abs(x - self.last[0]) + abs(y - self.last[1]) > 12:
            self.close()


def main(argv):
    if len(argv) > 1 and argv[1] == "stop":                 # hypridle runs this when you come back
        O.stop("screensaver")
        return 0
    args = [a for a in argv[1:] if not a.startswith("--")]
    seconds = 0
    if "--seconds" in argv:
        i = argv.index("--seconds")
        seconds = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 0
        args = [a for a in args if not a.isdigit()]
    style = args[0] if args else "stars"
    if style not in STYLES:
        print("usage: lennox-screensaver [stars|rain|aurora] [--seconds N]", file=sys.stderr)
        return 2
    O.claim("screensaver")
    app = Gtk.Application(application_id="dev.lennox.Screensaver")
    app.connect("activate", lambda a: (Window(style, seconds).set_application(a), a.get_windows()[0].present()))
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: app.quit() or False)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
