"""The session screen (SUPER + Escape, the power button in the bar), after end-4's.

    lennox-leave            open it
    lennox-leave --dry-run  open it, but only print what a button would run (tests)

The screen dims behind a blur, your picture and "See you soon, NAME" appear, and five
big buttons pop in one after another: Lock, Sleep, Log out, Restart, Shut down.
Arrow keys and Enter, a click, or the first letter (L, S, O, R, P) choose; Esc closes.
Log out, Restart and Shut down say goodbye first: the buttons fall away, the words
change and the screen fades to black, then it happens.
"""

import os
import sys
import time

from . import overlay as O
from . import profile as P
from . import settings as S
from .widgets.style import load_colors

Gtk, GLib, Gdk = O.Gtk, O.GLib, O.Gdk

# (key, label, icon, shortcut letter, command, says goodbye first)
ACTIONS = [
    ("lock", "Lock", "system-lock-screen-symbolic", "l", ["lennox-power", "lock"], False),
    ("sleep", "Sleep", "weather-clear-night-symbolic", "s", ["lennox-power", "suspend"], False),
    ("logout", "Log out", "system-log-out-symbolic", "o", ["lennox-power", "logout"], True),
    ("reboot", "Restart", "system-reboot-symbolic", "r", ["lennox-power", "reboot"], True),
    ("poweroff", "Shut down", "system-shutdown-symbolic", "p", ["lennox-power", "poweroff"], True),
]
FAREWELL = {"logout": "See you soon", "reboot": "Back in a moment", "poweroff": "Goodbye"}
STAGGER_MS = 45
GOODBYE_MS = 900

CSS = """
window.lennox-leave {{ background: transparent; }}
.leave-scrim {{ background-color: alpha(#000000, 0.0); transition: background-color 380ms cubic-bezier(0.05, 0.7, 0.1, 1); }}
.leave-scrim.shown {{ background-color: alpha(#000000, 0.45); }}
.leave-scrim.goodbye {{ background-color: alpha(#000000, 1.0); transition: background-color {goodbye}ms cubic-bezier(0.3, 0, 0.8, 0.15); }}
.leave-face {{ border-radius: 999px; border: 3px solid {primary}; }}
.leave-title {{ font-size: 34px; font-weight: 800; color: #ffffff; }}
.leave-sub {{ font-size: 15px; color: alpha(#ffffff, 0.75); }}
.leave-head {{ opacity: 0; transition: opacity 420ms ease, margin-top 600ms cubic-bezier(0.05, 0.7, 0.1, 1); margin-top: 24px; }}
.leave-head.shown {{ opacity: 1; margin-top: 0; }}
button.leave-button {{
    min-width: 118px; min-height: 118px; padding: 0; border-radius: 34px;
    background: alpha({surface_container_high}, 0.92); color: {on_surface};
    border: 1px solid alpha(#ffffff, 0.06); box-shadow: none;
    opacity: 0; margin-top: 30px;
    transition: opacity 360ms ease, margin-top 520ms cubic-bezier(0.05, 0.7, 0.1, 1),
                background-color 160ms ease, border-radius 260ms cubic-bezier(0.05, 0.7, 0.1, 1);
}}
button.leave-button.shown {{ opacity: 1; margin-top: 0; }}
button.leave-button:hover, button.leave-button:focus-visible, button.leave-button:focus {{
    background: {primary_container}; color: {on_primary_container}; border-radius: 26px;
}}
button.leave-button.danger:hover, button.leave-button.danger:focus {{ background: {error}; color: #2b0b0b; }}
button.leave-button.gone {{ opacity: 0; margin-top: 40px; }}
.leave-label {{ font-size: 14px; font-weight: 600; }}
.leave-key {{ font-size: 11px; opacity: 0.55; }}
"""


def uptime_text():
    try:
        with open("/proc/uptime") as f:
            seconds = int(float(f.read().split()[0]))
    except (OSError, ValueError):
        return ""
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return f"Up {hours} h {minutes} min" if hours else f"Up {minutes} min"


def subtitle():
    from .lockinfo import battery
    parts = [p for p in (uptime_text(), battery().replace("󰁹 ", "Battery ").replace("󰂄 ", "Charging ")) if p]
    return "  ·  ".join(parts)


class Leave(Gtk.ApplicationWindow):
    def __init__(self, app, dry_run=False):
        super().__init__(application=app, title="Lennox session", decorated=False)
        self.dry_run = dry_run
        self.leaving = False
        self.add_css_class("lennox-leave")
        O.css(CSS.format(goodbye=GOODBYE_MS, **load_colors()))
        settings = S.load()
        self.name = P.display_name(settings)

        self.scrim = Gtk.Box(css_classes=["leave-scrim"], hexpand=True, vexpand=True)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=26, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER)
        self.head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                            css_classes=["leave-head"])
        if os.path.exists(P.FACE):
            face = Gtk.Picture.new_for_filename(P.FACE)
            face.set_content_fit(Gtk.ContentFit.COVER)
            face.set_size_request(104, 104)
            frame = Gtk.Box(css_classes=["leave-face"], overflow=Gtk.Overflow.HIDDEN, halign=Gtk.Align.CENTER)
            frame.append(face)
            self.head.append(frame)
        self.title = Gtk.Label(label=f"See you soon, {self.name}", css_classes=["leave-title"])
        self.sub = Gtk.Label(label=subtitle(), css_classes=["leave-sub"])
        self.head.append(self.title)
        self.head.append(self.sub)
        column.append(self.head)

        row = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER)
        self.buttons = {}
        for key, label, icon, letter, _cmd, goodbye in ACTIONS:
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER)
            inner.append(Gtk.Image(icon_name=icon, pixel_size=36))
            inner.append(Gtk.Label(label=label, css_classes=["leave-label"]))
            inner.append(Gtk.Label(label=letter.upper(), css_classes=["leave-key"]))
            button = Gtk.Button(child=inner, css_classes=["leave-button"] + (["danger"] if key == "poweroff" else []),
                                tooltip_text=f"{label} ({letter.upper()})")
            button.connect("clicked", lambda _b, k=key: self.choose(k))
            row.append(button)
            self.buttons[key] = button
        column.append(row)

        overlay = Gtk.Overlay(child=self.scrim)
        overlay.add_overlay(column)
        self.set_child(overlay)
        if not O.configure(self, "lennox-session", "overlay", "exclusive"):
            self.set_default_size(1280, 720)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("released", lambda g, _n, x, y: self.close_soft() if g.get_widget().pick(x, y, 0) is self.scrim else None)
        overlay.add_controller(click)
        self.connect("map", lambda _w: GLib.timeout_add(30, self._enter))

    # ------------------------------------------------------------ motion

    def _enter(self):
        self.scrim.add_css_class("shown")
        self.head.add_css_class("shown")
        for i, (key, *_rest) in enumerate(ACTIONS):
            GLib.timeout_add(90 + i * STAGGER_MS, lambda k=key: self.buttons[k].add_css_class("shown") or False)
        GLib.timeout_add(90, lambda: self.buttons["lock"].grab_focus() or False)
        return False

    def close_soft(self):
        if self.leaving:
            return
        self.leaving = True
        self.scrim.remove_css_class("shown")
        self.head.remove_css_class("shown")
        for button in self.buttons.values():
            button.remove_css_class("shown")
        GLib.timeout_add(220, lambda: self.close() or False)

    def _key(self, _c, keyval, _code, _state):
        name = (Gdk.keyval_name(keyval) or "").lower()
        if name == "escape":
            self.close_soft()
            return True
        for key, _label, _icon, letter, _cmd, _g in ACTIONS:
            if name == letter:
                self.choose(key)
                return True
        return False

    # ------------------------------------------------------------ doing it

    def choose(self, key):
        if self.leaving:
            return
        action = next(a for a in ACTIONS if a[0] == key)
        command, goodbye = action[4], action[5]
        self.leaving = True
        self.chosen = key
        if not goodbye:
            # Lock and sleep: get out of the way fast
            self.scrim.remove_css_class("shown")
            for button in self.buttons.values():
                button.remove_css_class("shown")
            GLib.timeout_add(160, lambda: self._run(command, close=True) or False)
            return
        hour = time.localtime().tm_hour
        words = "See you tomorrow" if key == "poweroff" and (hour >= 20 or hour < 4) else FAREWELL[key]
        self.title.set_label(f"{words}, {self.name}")
        self.sub.set_label({"logout": "Logging out…", "reboot": "Restarting…", "poweroff": "Shutting down…"}[key])
        for i, button in enumerate(self.buttons.values()):
            GLib.timeout_add(i * 30, lambda b=button: b.add_css_class("gone") or False)
        self.scrim.add_css_class("goodbye")
        GLib.timeout_add(GOODBYE_MS + 150, lambda: self._run(command, close=False) or False)

    def _run(self, command, close):
        argv = [os.path.join(os.path.expanduser("~"), ".local", "bin", command[0])] + command[1:]
        if self.dry_run:
            print("RUN " + " ".join(command), flush=True)
        else:
            try:
                GLib.spawn_async(argv, flags=GLib.SpawnFlags.DEFAULT)
            except GLib.Error as e:
                print(f"lennox-leave: {e.message}", file=sys.stderr)
        if close or self.dry_run:
            self.close()


def main(argv):
    if O.running("leave"):
        O.stop("leave")             # the shortcut again closes it
        return 0
    O.claim("leave")
    dry = "--dry-run" in argv
    app = Gtk.Application(application_id="dev.lennox.Leave")
    app.connect("activate", lambda a: Leave(a, dry).present())
    return app.run([])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
