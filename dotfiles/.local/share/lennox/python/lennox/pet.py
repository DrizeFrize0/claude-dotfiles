"""Desktop pet: a small cat that walks along the bottom of the screen and sleeps when you are focusing or away.

    python3 -m lennox.pet start|stop|sync|run
    python3 -m lennox.pet across        the cat dashes across the screen once (an easter egg)

It sits above the bottom edge, lets clicks through, and costs almost nothing while asleep.
"""

import json
import os
import random
import signal
import subprocess
import sys
import time

from . import overlay as O
from . import settings as S

Gtk, GLib = O.Gtk, O.GLib
HEIGHT = 74
SLEEP_AFTER = 300          # seconds without the mouse moving


class Cat:
    """The pure part: where the cat is and what it's doing."""

    def __init__(self, width=1280, rng=random):
        self.rng, self.width = rng, width
        self.x, self.dir, self.state, self.t, self.until = width * 0.3, 1, "sit", 0.0, 2.0
        self.speed = 46.0

    def step(self, dt, asleep, width):
        self.width, self.t = width, self.t + dt
        if asleep:
            self.state = "sleep"
            return
        if self.state == "sleep":
            self.state, self.until, self.t = "sit", 1.0, 0.0
        if self.state == "dash":
            self.x += self.dir * 520 * dt
            if self.x < -60 or self.x > width + 60:
                self.state, self.until, self.t = "sit", 1.0, 0.0
                self.x = min(max(self.x, 20), width - 80)
            return
        if self.state == "walk":
            self.x += self.dir * self.speed * dt
            if self.x < 20 or self.x > width - 90:
                self.dir *= -1
        if self.t >= self.until:
            self.t = 0.0
            self.state = "sit" if self.state == "walk" else "walk"
            self.until = self.rng.uniform(2, 5) if self.state == "sit" else self.rng.uniform(4, 10)
            if self.state == "walk":
                self.dir = self.rng.choice((-1, 1))

    def dash(self, width):
        self.state, self.dir = "dash", 1
        self.x = -50.0


def draw_cat(snap, cat, base_y, color, t):
    """A cat from a few rounded rectangles: body, head, ears, tail and four legs."""
    x = cat.x
    flip = cat.dir
    walking = cat.state in ("walk", "dash")
    swing = (1 if int(t * (14 if cat.state == "dash" else 7)) % 2 else -1) if walking else 0

    def px(dx):                       # mirror around the cat's middle when it walks left
        return x + 30 + (dx - 30) * flip

    if cat.state == "sleep":
        O.fill(snap, x, base_y - 20, 64, 20, color, 10)                 # a curled-up loaf
        O.fill(snap, x + 44, base_y - 28, 22, 18, color, 9)
        O.fill(snap, x + 48, base_y - 36, 5, 8, color, 2)
        O.fill(snap, x + 58, base_y - 36, 5, 8, color, 2)
        for i in range(3):                                              # little z's drifting up
            k = (t * 0.6 + i / 3) % 1
            O.disc(snap, x + 70 + i * 6, base_y - 34 - k * 26, 2 + i, O.rgba(0.8, 0.85, 1.0, 0.6 * (1 - k)))
        return
    bob = 2 * swing if walking else 0
    O.fill(snap, min(px(10), px(48)), base_y - 28 + bob / 2, 38, 18, color, 9)                   # body
    O.fill(snap, min(px(45), px(61)), base_y - 40 + bob / 2, 16, 16, color, 8)                    # head
    for ear in (47, 55):
        O.fill(snap, px(ear) - 2, base_y - 47 + bob / 2, 5, 8, color, 2)                         # ears
    tail_up = 18 if cat.state == "sit" else 12 + 4 * swing
    O.fill(snap, px(8) - (2 if flip > 0 else -2), base_y - 26 - tail_up, 5, 20 + tail_up, color, 3)   # tail
    for i, dx in enumerate((14, 22, 36, 44)):
        lift = (swing if i % 2 else -swing) * 3 if walking else 0
        O.fill(snap, px(dx) - 2, base_y - 12 - max(lift, 0), 5, 12 + min(lift, 0) * -1, color, 2)   # legs
    O.disc(snap, px(58), base_y - 33 + bob / 2, 1.6, O.rgba(1, 1, 1, 0.9))                     # eye


class Window(Gtk.Window):
    def __init__(self):
        super().__init__(title="Lennox pet", decorated=False, default_width=1280, default_height=HEIGHT)
        self.add_css_class("lennox-overlay")
        O.css(O.TRANSPARENT)
        self.cat = Cat()
        self.last_pos, self.last_move = None, time.monotonic()
        self.canvas = O.Canvas(self.draw, self.step, fps=15)
        self.set_child(self.canvas)
        O.configure(self, "lennox-pet", "bottom", "none", ("bottom", "left", "right"), -1)
        O.click_through(self)

    def asleep(self):
        try:
            with open(os.path.join(S.STATE_DIR, "focus.json"), encoding="utf-8") as f:
                if json.load(f).get("phase") == "focus":
                    return True
        except (OSError, ValueError, AttributeError):
            pass
        if subprocess.run(["pidof", "hyprlock"], capture_output=True, check=False).returncode == 0:
            return True
        return time.monotonic() - self.last_move > SLEEP_AFTER

    def step(self, dt, w, _h):
        pos = O.cursor_pos()
        if pos and pos != self.last_pos:
            self.last_pos, self.last_move = pos, time.monotonic()
        self.cat.step(dt, self.asleep() and self.cat.state != "dash", w or 1280)

    def draw(self, snap, w, h):
        r, g, b = O.accent()
        draw_cat(snap, self.cat, h - 2, O.rgba(0.12 + r * 0.25, 0.12 + g * 0.25, 0.14 + b * 0.25, 0.95), self.cat.t * 1.0 + time.monotonic())


def run(dash_only=False):
    O.claim("pet")
    app = Gtk.Application(application_id="dev.lennox.Pet")

    def activate(a):
        win = Window()
        win.set_application(a)
        win.present()
        win.canvas.start()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: win.cat.dash(win.get_width()) or True)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: a.quit() or False)
        if dash_only:
            win.cat.dash(win.get_width())
            GLib.timeout_add(500, lambda: (a.quit() if win.cat.state != "dash" else None) or win.cat.state == "dash")
    app.connect("activate", activate)
    return app.run([])


def across():
    """The cat dashes across: through the running pet, or a one-off one when the pet is off."""
    pid = O.running("pet")
    if pid:
        os.kill(pid, signal.SIGUSR1)
        return 0
    return run(dash_only=True)


def main(argv):
    if len(argv) > 1 and argv[1] == "across":
        return across()
    code = O.serve("pet", "pet.on", argv, run)
    if code is None:
        print("usage: lennox-pet start | stop | sync | across", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
