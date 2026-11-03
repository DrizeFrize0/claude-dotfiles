"""Welcome animation at login: stars drift in, "Welcome back, NAME" fades up, then it all fades away.

    python3 -m lennox.loginanim [--seconds N]

Plays once when the desktop starts (about 4 seconds). Any key or click skips it.
Settings > Daily care > Greeting turns it off.
"""

import getpass
import os
import math
import random
import sys
import time

from . import greeting as G
from . import overlay as O
from . import screensaver as SS
from . import settings as S

Gtk, GLib = O.Gtk, O.GLib
FADE_IN, FADE_OUT = 0.9, 0.9


def envelope(t, total):
    """0..1: fades in, holds, fades out."""
    if t < 0 or t > total:
        return 0.0
    if t < FADE_IN:
        return t / FADE_IN
    if t > total - FADE_OUT:
        return max(0.0, (total - t) / FADE_OUT)
    return 1.0


def ease(x):
    return x * x * (3 - 2 * x)


class Window(Gtk.Window):
    def __init__(self, total):
        super().__init__(title="Lennox welcome", decorated=False)
        self.add_css_class("lennox-overlay")
        O.css(O.TRANSPARENT + " label.login-title { font-size: 56px; font-weight: 800; color: #eef2ff; } "
              "label.login-sub { font-size: 20px; color: #a9bbea; }")
        self.total, self.t0 = total, time.monotonic()
        self.stars = SS.Stars(160, random.Random())
        self.level = 0.0
        self.canvas = O.Canvas(self.draw, self.step, fps=40)
        settings = S.load()
        name = settings["greeting"]["name"].strip() or getpass.getuser().capitalize()
        title = Gtk.Label(label=f"{G.hello(time.localtime().tm_hour)}, {name}", css_classes=["login-title"])
        sub = Gtk.Label(label=time.strftime("%A %-d %B  ·  %H:%M"), css_classes=["login-sub"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        logo = os.path.expanduser("~/.config/lennox/assets/logo/lennox-logo-256.png")
        if os.path.exists(logo):                       # the Lennox logo above the words
            picture = Gtk.Image.new_from_paintable(O.Gdk.Texture.new_from_filename(logo))
            picture.set_pixel_size(128)               # an Image is drawn exactly this big
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_margin_bottom(14)
            box.append(picture)
        box.append(title)
        box.append(sub)
        self.box = box
        overlay = Gtk.Overlay(child=self.canvas)
        overlay.add_overlay(box)
        self.set_child(overlay)
        if not O.configure(self, "lennox-welcome", "overlay", "exclusive"):
            self.set_default_size(960, 600)
        for controller, signal in ((Gtk.EventControllerKey(), "key-pressed"), (Gtk.GestureClick(), "pressed")):
            controller.connect(signal, lambda *_a: self.close() or True)
            self.add_controller(controller)
        self.canvas.start()

    def step(self, dt, _w, _h):
        t = time.monotonic() - self.t0
        self.level = ease(envelope(t, self.total))
        self.stars.step(dt)
        # the text comes in a little after the sky and leaves a little before it
        self.box.set_opacity(ease(envelope(t - 0.35, self.total - 0.7)))
        if t > self.total:
            self.close()

    def draw(self, snap, w, h):
        a = self.level
        O.fill(snap, 0, 0, w, h, O.rgba(0.01, 0.015, 0.05, 0.97 * a))
        r, g, b = O.accent()
        # a soft glow behind the words
        rect = O.Graphene.Rect().init(0, 0, w, h)
        snap.append_radial_gradient(rect, O.Graphene.Point().init(w / 2, h / 2), w * 0.45, h * 0.35, 0.0, 1.0,
                                    [O.cstop(0.0, O.rgba(r, g, b, 0.22 * a)), O.cstop(1.0, O.rgba(r, g, b, 0.0))])
        for x, y, size, phase, _v in self.stars.stars:
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self.stars.t * 1.3 + phase))
            O.disc(snap, x * w, y * h, size, O.rgba(0.85, 0.9, 1.0, tw * a))


def main(argv):
    total = 4.0
    if "--seconds" in argv:
        i = argv.index("--seconds")
        total = float(argv[i + 1]) if i + 1 < len(argv) else total
    if "--force" not in argv and not S.load()["greeting"]["animation"]:
        return 0
    app = Gtk.Application(application_id="dev.lennox.LoginAnim")
    app.connect("activate", lambda a: (Window(total).set_application(a), a.get_windows()[0].present()))
    return app.run([])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
