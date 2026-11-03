"""Cursor effects: a glowing trail, a spotlight for screen sharing, and a ring on every click.

    python3 -m lennox.cursorfx start|stop|sync|run
    python3 -m lennox.cursorfx ripple        (the mouse button runs this) a ring at the cursor

Hyprland says where the mouse is; this draws on a see-through layer on top of
everything and lets every click and key through.
"""

import os
import signal
import sys
import time

from . import overlay as O

Gtk, GLib = O.Gtk, O.GLib
TRAIL_LIFE = 0.45
RIPPLE_LIFE = 0.55


class Effects:
    """The pure part: points that fade, rings that grow."""

    def __init__(self):
        self.trail, self.ripples = [], []

    def move(self, x, y, now):
        if not self.trail or abs(self.trail[-1][0] - x) + abs(self.trail[-1][1] - y) > 3:
            self.trail.append((x, y, now))

    def ripple(self, x, y, now):
        self.ripples.append((x, y, now))

    def prune(self, now):
        self.trail = [p for p in self.trail if now - p[2] < TRAIL_LIFE]
        self.ripples = [p for p in self.ripples if now - p[2] < RIPPLE_LIFE]

    def busy(self, now):
        return bool(self.trail or self.ripples)


class Window(Gtk.Window):
    def __init__(self, settings):
        super().__init__(title="Lennox cursor effects", decorated=False, default_width=1280, default_height=800)
        self.add_css_class("lennox-overlay")
        O.css(O.TRANSPARENT)
        self.style, self.ripples_on = settings["style"], settings["ripple"]
        self.fx = Effects()
        self.pos = (-100, -100)
        self.canvas = O.Canvas(self.draw, self.step, fps=60)
        self.set_child(self.canvas)
        O.configure(self, "lennox-cursorfx", "overlay", "none")
        O.click_through(self)

    def step(self, _dt, _w, _h):
        now = time.monotonic()
        pos = O.cursor_pos()
        if pos:
            self.pos = pos
            if self.style == "trail":
                self.fx.move(pos[0], pos[1], now)
        self.fx.prune(now)

    def ripple(self):
        self.fx.ripple(self.pos[0], self.pos[1], time.monotonic())

    def draw(self, snap, w, h):
        r, g, b = O.accent()
        now = time.monotonic()
        if self.style == "spotlight":
            x, y = self.pos
            rect = O.Graphene.Rect().init(0, 0, w, h)
            snap.append_radial_gradient(rect, O.Graphene.Point().init(x, y), 330, 330, 0.0, 1.0,
                                        [O.cstop(0.0, O.rgba(0, 0, 0, 0.0)), O.cstop(0.55, O.rgba(0, 0, 0, 0.0)),
                                         O.cstop(1.0, O.rgba(0, 0, 0, 0.55))])
        for x, y, t in self.fx.trail:
            life = 1 - (now - t) / TRAIL_LIFE
            O.disc(snap, x, y, 3 + 9 * life, O.rgba(r, g, b, 0.35 * life))
        for x, y, t in self.fx.ripples:
            life = (now - t) / RIPPLE_LIFE
            O.ring(snap, x, y, 8 + 46 * life, 3, O.rgba(r, g, b, 0.8 * (1 - life)))


def run():
    O.claim("cursorfx")
    settings = O.S.load()["cursorfx"]
    app = Gtk.Application(application_id="dev.lennox.CursorFx")

    def activate(a):
        win = Window(settings)
        win.set_application(a)
        win.present()
        win.canvas.start()
        if settings["ripple"]:
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: win.ripple() or True)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: a.quit() or False)
    app.connect("activate", activate)
    return app.run([])


def main(argv):
    if len(argv) > 1 and argv[1] == "ripple":
        pid = O.running("cursorfx")
        if pid:
            os.kill(pid, signal.SIGUSR1)
        return 0
    code = O.serve("cursorfx", "cursorfx.on", argv, run)
    if code is None:
        print("usage: lennox-cursorfx start | stop | sync | ripple", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
