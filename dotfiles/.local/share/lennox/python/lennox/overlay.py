"""Shared pieces for Lennox's screen overlays (screensaver, music wallpaper, cursor effects, pet, games).

They draw with GTK's own render nodes (rounded rectangles and gradients), so they need
no extra drawing library, and are started and stopped by name:

    lennox-pet start|stop|sync|run      (the same for visualizer, cursorfx)
"""

import ctypes
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time

LAYER_SHELL = False
if not os.environ.get("LENNOX_WIDGETS_NO_LAYER"):
    for _lib in ("libgtk4-layer-shell.so", "libgtk4-layer-shell.so.0"):
        try:
            ctypes.CDLL(_lib)                 # before GTK loads libwayland-client
            LAYER_SHELL = True
            break
        except OSError:
            pass

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk  # noqa: E402

LS = None
if LAYER_SHELL:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LS  # noqa: E402
    except (ValueError, ImportError):
        LAYER_SHELL = False

from . import settings as S  # noqa: E402

ALL = ("top", "bottom", "left", "right")


def rgba(r, g, b, a=1.0):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = r, g, b, a
    return c


def accent(default=(0.66, 0.78, 1.0)):
    """The theme's main color as (r, g, b) floats, read from the bar's color file."""
    try:
        with open(os.path.expanduser("~/.config/waybar/colors.css"), encoding="utf-8") as f:
            m = re.search(r"@define-color\s+primary\s+#([0-9a-fA-F]{6})", f.read())
        if m:
            h = m.group(1)
            return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except OSError:
        pass
    return default


def configure(win, namespace, layer="overlay", keyboard="none", anchors=ALL, exclusive=-1, margins=None):
    """Turns a window into a screen layer. False when not on a Wayland compositor with layer-shell (tests)."""
    if not (LAYER_SHELL and LS.is_supported()):
        return False
    LS.init_for_window(win)
    LS.set_namespace(win, namespace)
    LS.set_layer(win, {"overlay": LS.Layer.OVERLAY, "top": LS.Layer.TOP, "bottom": LS.Layer.BOTTOM,
                       "background": LS.Layer.BACKGROUND}[layer])
    LS.set_keyboard_mode(win, {"none": LS.KeyboardMode.NONE, "exclusive": LS.KeyboardMode.EXCLUSIVE,
                               "demand": LS.KeyboardMode.ON_DEMAND}[keyboard])
    LS.set_exclusive_zone(win, exclusive)
    edges = {"top": LS.Edge.TOP, "bottom": LS.Edge.BOTTOM, "left": LS.Edge.LEFT, "right": LS.Edge.RIGHT}
    for name, edge in edges.items():
        LS.set_anchor(win, edge, name in anchors)
    for name, value in (margins or {}).items():
        LS.set_margin(win, edges[name], value)
    return True


def click_through(win):
    """Clicks go to the window below (an empty input region)."""
    try:
        import cairo
    except ImportError:
        return

    def realized(w):
        surface = w.get_surface()
        if surface is not None:
            surface.set_input_region(cairo.Region())
    win.connect("realize", realized)


# ---------------------------------------------------------------- drawing

def fill(snap, x, y, w, h, color, radius=0.0):
    rect = Graphene.Rect().init(x, y, w, h)
    if radius > 0:
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect, min(radius, w / 2, h / 2))
        snap.push_rounded_clip(rr)
        snap.append_color(color, rect)
        snap.pop()
    else:
        snap.append_color(color, rect)


def disc(snap, cx, cy, r, color):
    fill(snap, cx - r, cy - r, 2 * r, 2 * r, color, r)


def ring(snap, cx, cy, r, width, color):
    rect = Graphene.Rect().init(cx - r, cy - r, 2 * r, 2 * r)
    rr = Gsk.RoundedRect()
    rr.init_from_rect(rect, r)
    snap.append_border(rr, [width] * 4, [color] * 4)


def cstop(offset, color):
    s = Gsk.ColorStop()
    s.offset, s.color = offset, color
    return s


class Canvas(Gtk.Widget):
    """A widget that calls draw(snapshot, width, height) up to `fps` times a second while `running`."""

    __gtype_name__ = "LennoxCanvas"

    def __init__(self, draw, step=None, fps=30):
        super().__init__(hexpand=True, vexpand=True)
        self.draw, self.step, self.interval = draw, step, 1_000_000 // fps
        self.last = 0
        self.tick_id = None

    def start(self):
        if self.tick_id is None:
            self.tick_id = self.add_tick_callback(self._tick)

    def stop(self):
        if self.tick_id is not None:
            self.remove_tick_callback(self.tick_id)
            self.tick_id = None

    def _tick(self, _w, clock):
        now = clock.get_frame_time()
        if now - self.last >= self.interval:
            dt = min((now - self.last) / 1e6, 0.2) if self.last else 0.0
            self.last = now
            if self.step:
                self.step(dt, self.get_width(), self.get_height())
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def do_snapshot(self, snapshot):
        self.draw(snapshot, self.get_width(), self.get_height())


class Cached:
    """fn() remembered for `ttl` seconds: for checks that must not run on every frame (starting a program, reading a file)."""

    def __init__(self, fn, ttl, clock=time.monotonic):
        self.fn, self.ttl, self.clock = fn, ttl, clock
        self.at, self.value = None, None

    def __call__(self):
        now = self.clock()
        if self.at is None or now - self.at >= self.ttl:
            self.at, self.value = now, self.fn()
        return self.value


def css(text):
    provider = Gtk.CssProvider()
    provider.load_from_string(text)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


TRANSPARENT = "window.lennox-overlay { background: transparent; }"


# ---------------------------------------------------------------- Hyprland

def hypr_socket():
    base = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "hypr")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        try:
            sig = sorted(os.listdir(base), key=lambda d: os.path.getmtime(os.path.join(base, d)))[-1]
        except (OSError, IndexError):
            return None
    return os.path.join(base, sig, ".socket.sock")


def cursor_pos():
    """(x, y) of the mouse in the desktop, asked straight from Hyprland (cheap enough to do 60 times a second)."""
    path = hypr_socket()
    if not path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect(path)
            s.sendall(b"j/cursorpos")
            data = json.loads(s.recv(4096).decode())
        return data["x"], data["y"]
    except (OSError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------- start / stop by name

def pidfile(name):
    return os.path.join(S.RUNTIME_DIR, f"{name}.pid")


def running(name):
    try:
        with open(pidfile(name), encoding="utf-8") as f:
            pid = int(f.read())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def start(name):
    if running(name):
        return
    subprocess.Popen([sys.executable, "-m", f"lennox.{name}", "run"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def stop(name):
    pid = running(name)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        os.remove(pidfile(name))
    except OSError:
        pass


def claim(name):
    """Writes this process's pid so start/stop can find it."""
    os.makedirs(os.path.dirname(pidfile(name)), exist_ok=True)
    with open(pidfile(name), "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def serve(name, setting, argv, run):
    """The usual start/stop/sync/run commands for an overlay tool. `setting` is the on/off path."""
    mode = argv[1] if len(argv) > 1 else "sync"
    if mode == "run":
        return run()
    if mode == "start":
        start(name)
    elif mode == "stop":
        stop(name)
    elif mode == "sync":
        section, _, key = setting.partition(".")
        (start if S.load()[section][key] else stop)(name)
    else:
        return None
    return 0
