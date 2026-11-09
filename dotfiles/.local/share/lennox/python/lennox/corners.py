"""Rounded screen corners, after end-4's: the four corners of every screen are drawn
round (a tiny black quarter-circle mask in each), so the desktop looks like a phone's
screen. Clicks go straight through; fullscreen games and videos cover them.

    lennox-corners start | stop | sync      (Lennox Settings > Appearance > Rounded screen corners)
"""

import sys

from . import overlay as O
from . import settings as S

Gtk, GLib, Gdk = O.Gtk, O.GLib, O.Gdk
CORNERS = {"top-left": ("top", "left"), "top-right": ("top", "right"),
           "bottom-left": ("bottom", "left"), "bottom-right": ("bottom", "right")}


def mask_centre(corner, r):
    """Where the round edge's circle is centred inside the r x r square."""
    vertical, horizontal = CORNERS[corner]
    return (r if horizontal == "left" else 0.0), (r if vertical == "top" else 0.0)


def draw_mask(snap, corner, r):
    """Black outside the quarter circle, clear inside: a circle centred on the screen side
    of the square, with a solid "shadow" spreading r pixels outward (GTK render nodes)."""
    cx, cy = mask_centre(corner, r)
    circle = O.Gsk.RoundedRect()
    circle.init_from_rect(O.Graphene.Rect().init(cx - r, cy - r, 2 * r, 2 * r), r)
    snap.append_outset_shadow(circle, O.rgba(0, 0, 0, 1), 0, 0, r + 1, 0)


class Corner(Gtk.Window):
    def __init__(self, app, corner, radius, monitor=None):
        super().__init__(application=app, title=f"Lennox corner {corner}", decorated=False)
        self.add_css_class("lennox-overlay")
        canvas = O.Canvas(lambda snap, _w, _h: draw_mask(snap, corner, radius))
        canvas.set_size_request(radius, radius)
        self.set_child(canvas)
        self.set_default_size(radius, radius)
        if O.configure(self, "lennox-corners", "top", "none", anchors=CORNERS[corner], exclusive=-1):
            if monitor is not None:
                O.LS.set_monitor(self, monitor)
        O.click_through(self)


def run():
    O.claim("corners")
    radius = max(6, min(40, int(S.load()["corners"]["radius"])))
    app = Gtk.Application(application_id="dev.lennox.Corners")

    def activate(a):
        O.css(O.TRANSPARENT)
        a.hold()
        monitors = Gdk.Display.get_default().get_monitors()
        targets = [monitors.get_item(i) for i in range(monitors.get_n_items())] or [None]
        for monitor in targets:
            for corner in CORNERS:
                Corner(a, corner, radius, monitor).present()

    app.connect("activate", activate)
    return app.run([])


def main(argv):
    code = O.serve("corners", "corners.on", argv, run)
    if code is None:
        print("usage: lennox-corners start | stop | sync", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
