"""Lennox widgets: desktop widgets and the dashboard (SUPER + D).

One background process (started at login) owns both. Later calls of
`lennox-widgets ...` are forwarded to it over D-Bus:

    lennox-widgets                      start (at login)
    lennox-widgets dashboard [toggle|open|close]
    lennox-widgets desktop [toggle|on|off]
    lennox-widgets reload               re-read settings and colors
    lennox-widgets quit
"""

import ctypes
import os
import sys

# gtk4-layer-shell must be loaded before GTK pulls in libwayland-client
LAYER_SHELL = False
if not os.environ.get("LENNOX_WIDGETS_NO_LAYER"):
    for _lib in ("libgtk4-layer-shell.so", "libgtk4-layer-shell.so.0"):
        try:
            ctypes.CDLL(_lib)
            LAYER_SHELL = True
            break
        except OSError:
            pass

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

if LAYER_SHELL:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LS  # noqa: E402
    except (ValueError, ImportError):
        LAYER_SHELL = False

from .. import settings as S  # noqa: E402
from . import cards, style  # noqa: E402
from .mpris import Mpris  # noqa: E402

APP_ID = "dev.lennox.Widgets"
DASHBOARD_WIDTH = 400


class Settings:
    """settings.json, re-read on `reload` and when the file changes."""

    def __init__(self):
        self.data = S.load()

    def reload(self):
        self.data = S.load()

    def get(self, path):
        return S.get(self.data, path)


def layer_shell_ready(window):
    return LAYER_SHELL and LS.is_supported()


# ---------------------------------------------------------------- desktop

class DesktopWindow(Gtk.ApplicationWindow):
    """Widgets on the wallpaper, below your windows."""

    MARGIN = 28

    def __init__(self, app):
        super().__init__(application=app, title="Lennox Widgets")
        self.app = app
        self.add_css_class("lennox-widgets")
        self.set_decorated(False)
        self.cards = []
        if layer_shell_ready(self):
            LS.init_for_window(self)
            LS.set_namespace(self, "lennox-widgets")
            LS.set_layer(self, LS.Layer.BOTTOM)
            LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)
            LS.set_exclusive_zone(self, 0)
        self.build()

    def build(self):
        for card in self.cards:
            card.stop()
        st = self.app.settings
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.cards = []
        if st.get("widgets.show_clock"):
            self.cards.append(cards.ClockCard(st, framed=False, greeting=st.get("widgets.show_greeting")))
        if st.get("widgets.show_weather") and st.get("widgets.weather_city").strip():
            self.cards.append(cards.WeatherCard(st, hide_on_error=True))
        if st.get("widgets.show_media"):
            self.cards.append(cards.MediaCard(self.app.mpris, hide_when_idle=True))
        if st.get("widgets.show_system"):
            self.cards.append(cards.SystemCard(title=None))
        for card in self.cards:
            if not isinstance(card, cards.ClockCard):
                card.set_size_request(320, -1)
            box.append(card)
        self.set_child(box)
        self.place(st.get("widgets.position"), box)
        for card in self.cards:
            card.start()

    def place(self, position, box):
        vertical, _, horizontal = position.partition("-")
        if position == "center":
            vertical, horizontal = "center", "center"
        right = horizontal == "right"
        center = horizontal == "center"
        box.set_halign(Gtk.Align.END if right else (Gtk.Align.CENTER if center else Gtk.Align.START))
        for child in self.cards:
            child.set_halign(Gtk.Align.END if right else (Gtk.Align.CENTER if center else Gtk.Align.START))
        for card in self.cards:
            if isinstance(card, cards.ClockCard):
                xalign = 1.0 if right else (0.5 if center else 0.0)
                for lbl in (card.date, card.greeting):
                    lbl.set_xalign(xalign)
        if not layer_shell_ready(self):
            return
        edges = {
            LS.Edge.TOP: vertical == "top",
            LS.Edge.BOTTOM: vertical == "bottom",
            LS.Edge.LEFT: horizontal == "left",
            LS.Edge.RIGHT: horizontal == "right",
        }
        for edge, on in edges.items():
            LS.set_anchor(self, edge, on)
            LS.set_margin(self, edge, self.MARGIN if on else 0)
        if vertical == "bottom":
            # Leave room for the dock
            LS.set_margin(self, LS.Edge.BOTTOM, self.MARGIN + 70)

    def stop(self):
        for card in self.cards:
            card.stop()


# ---------------------------------------------------------------- dashboard

class DashboardWindow(Gtk.ApplicationWindow):
    """The sidebar: you, quick actions, sliders, music, weather, calendar, notes.

    The window covers the screen (transparent) so a click next to the
    panel closes it, like a menu.
    """

    def __init__(self, app):
        super().__init__(application=app, title="Lennox Dashboard")
        self.app = app
        self.add_css_class("lennox-dashboard-window")
        self.set_decorated(False)
        self.set_hide_on_close(True)
        self.cards = []
        self.layer = layer_shell_ready(self)
        if self.layer:
            LS.init_for_window(self)
            LS.set_namespace(self, "lennox-dashboard")
            LS.set_layer(self, LS.Layer.OVERLAY)
            for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
                LS.set_anchor(self, edge, True)
            LS.set_keyboard_mode(self, LS.KeyboardMode.EXCLUSIVE)
            LS.set_exclusive_zone(self, 0)
        else:
            self.set_default_size(DASHBOARD_WIDTH + 20, 820)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)

        root = Gtk.Box()
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.add_css_class("lennox-dashboard")
        self.panel.set_size_request(DASHBOARD_WIDTH, -1)
        for side in ("top", "bottom", "start"):
            getattr(self.panel, f"set_margin_{side}")(10)
        root.append(self.panel)
        catcher = Gtk.Box(hexpand=True, vexpand=True)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_a: self.close_dashboard())
        catcher.add_controller(click)
        root.append(catcher)
        self.set_child(root)
        self.build()

    def build(self):
        for card in self.cards:
            card.stop()
        st = self.app.settings
        close = self.close_dashboard
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        clock = cards.ClockCard(st, framed=False, greeting=False)
        self.cards = [
            cards.HeaderCard(st, close),
            clock,
            cards.ActionsCard(close),
            cards.SlidersCard(),
            cards.MediaCard(self.app.mpris, hide_when_idle=False, title="Now playing"),
            cards.WeatherCard(st, detailed=True),
            cards.CalendarCard(),
            cards.SystemCard(),
            cards.NotesCard(),
        ]
        for card in self.cards:
            content.append(card)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(content)
        child = self.panel.get_first_child()
        while child:
            self.panel.remove(child)
            child = self.panel.get_first_child()
        self.panel.append(scroller)
        if self.get_visible():
            for card in self.cards:
                card.start()

    def _key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close_dashboard()
            return True
        return False

    def open_dashboard(self):
        if self.get_visible():
            return
        for card in self.cards:
            card.start()
        self.present()

    def close_dashboard(self):
        if not self.get_visible():
            return
        for card in self.cards:
            card.stop()
        self.set_visible(False)

    def toggle(self):
        if self.get_visible():
            self.close_dashboard()
        else:
            self.open_dashboard()


# ---------------------------------------------------------------- app

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.settings = Settings()
        self.mpris = Mpris()
        self.desktop = None
        self.dashboard = None
        self.css = None
        self.started = False
        self.monitors = []

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # keep running with no window open (desktop widgets off)
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.load_css()
        # Live updates: new wallpaper colors, settings changed elsewhere
        for path, callback in ((style.COLORS_FILE, self.load_css), (style.CUSTOM_CSS, self.load_css),
                               (S.SETTINGS_FILE, self.reload)):
            monitor = Gio.File.new_for_path(path).monitor_file(Gio.FileMonitorFlags.WATCH_MOVES, None)
            monitor.set_rate_limit(500)
            monitor.connect("changed", self._file_changed, callback)
            self.monitors.append(monitor)

    def _file_changed(self, _monitor, _file, _other, event, callback):
        if event in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                     Gio.FileMonitorEvent.MOVED_IN, Gio.FileMonitorEvent.RENAMED):
            if not getattr(self, "_debounce", 0):
                self._debounce = GLib.timeout_add(300, self._run_debounced, callback)

    def _run_debounced(self, callback):
        self._debounce = 0
        callback()
        return GLib.SOURCE_REMOVE

    def load_css(self):
        text = style.css()
        try:
            self.css.load_from_string(text)
        except AttributeError:  # GTK < 4.12
            self.css.load_from_data(text, -1)

    def reload(self):
        before = self.settings.data.get("widgets"), self.settings.data["bar"]["clock_24h"]
        self.settings.reload()
        after = self.settings.data.get("widgets"), self.settings.data["bar"]["clock_24h"]
        if before != after:
            self.apply_desktop()
            if self.dashboard:
                self.dashboard.build()
        self.load_css()

    def apply_desktop(self):
        enabled = self.settings.get("widgets.desktop")
        if enabled:
            if self.desktop is None:
                self.desktop = DesktopWindow(self)
            else:
                self.desktop.build()
            self.desktop.present()
        elif self.desktop is not None:
            self.desktop.stop()
            self.desktop.destroy()
            self.desktop = None

    def do_command_line(self, command_line):
        # Always answer: a caller waits for this (an exception here would
        # leave `lennox-widgets ...` hanging)
        try:
            return self._command(command_line.get_arguments()[1:], command_line)
        except Exception as e:  # noqa: BLE001
            print(f"lennox-widgets: {e!r}", file=sys.stderr)
            return 1

    def _command(self, args, command_line):
        first_run = not self.started
        self.started = True
        if first_run and args[:1] == ["quit"]:
            self.quit()
            return 0
        if first_run:
            self.dashboard = DashboardWindow(self)
            self.apply_desktop()
        cmd = args[0] if args else ""
        if cmd == "dashboard":
            action = args[1] if len(args) > 1 else "toggle"
            {"open": self.dashboard.open_dashboard, "close": self.dashboard.close_dashboard}.get(
                action, self.dashboard.toggle)()
        elif cmd == "desktop":
            # Show / hide the desktop widgets and remember it (SUPER + CTRL + W)
            action = args[1] if len(args) > 1 else "toggle"
            value = {"on": True, "off": False}.get(action, not self.settings.get("widgets.desktop"))
            S.set_value("widgets.desktop", value)
            self.reload()
        elif cmd == "reload" and not first_run:
            self.reload()
        elif cmd == "quit":
            self.quit()
        elif cmd not in ("", "reload", "start"):
            message = (f"lennox-widgets: unknown command '{cmd}'\n"
                       "usage: lennox-widgets [dashboard [toggle|open|close] | desktop [toggle|on|off] | reload | quit]\n")
            if hasattr(command_line, "printerr_literal"):
                command_line.printerr_literal(message)
            else:
                print(message, end="", file=sys.stderr)
            return 2
        return 0


def main(argv=None):
    if not os.environ.get("LENNOX_WIDGETS_NO_LAYER"):
        # Without layer shell the widgets would open as normal windows: don't
        if not LAYER_SHELL:
            print("lennox-widgets: gtk4-layer-shell is missing (sudo pacman -S gtk4-layer-shell)", file=sys.stderr)
            return 1
        if not LS.is_supported():
            print("lennox-widgets: needs a Wayland session (Hyprland)", file=sys.stderr)
            return 1
    return App().run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
