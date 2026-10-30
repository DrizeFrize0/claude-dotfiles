"""Lennox Settings: one window to control the whole desktop.

    lennox-settings                 open (or focus) the window
    lennox-settings --page NAME     open on a page, e.g. wallpaper, sound, updates
"""

import importlib
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import VERSION  # noqa: E402
from .store import Store  # noqa: E402

APP_ID = "dev.lennox.Settings"

# (page id, title, icon, module in lennox.app.pages)
PAGES = [
    ("welcome", "Welcome", "user-home-symbolic", "welcome"),
    ("appearance", "Appearance", "applications-graphics-symbolic", "appearance"),
    ("wallpaper", "Wallpaper", "preferences-desktop-wallpaper-symbolic", "wallpaper"),
    ("bar", "Bar & Dock", "view-grid-symbolic", "bar"),
    ("widgets", "Widgets", "view-app-grid-symbolic", "widgets"),
    ("sound", "Sound", "audio-volume-high-symbolic", "sound"),
    ("display", "Display", "video-display-symbolic", "display"),
    ("input", "Keyboard & Touchpad", "input-keyboard-symbolic", "input"),
    ("connections", "Wi-Fi & Bluetooth", "network-wireless-symbolic", "connections"),
    ("phone", "Phone", "phone-symbolic", "phone"),
    ("power", "Power & Battery", "battery-good-symbolic", "power"),
    ("night", "Night", "weather-clear-night-symbolic", "night"),
    ("focus", "Focus", "find-location-symbolic", "focus"),
    ("games", "Game Center", "input-gaming-symbolic", "games"),
    ("graphics", "Graphics", "applications-games-symbolic", "graphics"),
    ("store", "App Store", "system-software-install-symbolic", "store"),
    ("apps", "Default Apps", "applications-system-symbolic", "apps"),
    ("updates", "Updates", "software-update-available-symbolic", "updates"),
    ("cleanup", "Cleanup", "user-trash-symbolic", "cleanup"),
    ("passwords", "Passwords", "dialog-password-symbolic", "passwords"),
    ("keybinds", "Keybindings", "preferences-desktop-keyboard-shortcuts-symbolic", "keybinds"),
    ("health", "Health Check", "emblem-ok-symbolic", "health"),
    ("about", "About", "help-about-symbolic", "about"),
]
PAGE_IDS = [p[0] for p in PAGES]


class Context:
    """What every page gets: the settings store and a few window helpers."""

    def __init__(self, window, store):
        self.window = window
        self.store = store

    def toast(self, text, timeout=3):
        self.window.toast(text, timeout)

    def navigate(self, page_id):
        self.window.show_page(page_id)


class Window(Adw.ApplicationWindow):
    def __init__(self, app, store):
        super().__init__(application=app, title="Lennox Settings")
        self.set_default_size(1080, 720)
        self.set_size_request(360, 400)
        self.store = store
        self.ctx = Context(self, store)
        self.pages = {}          # id -> page object (built on first visit)
        self.rows = {}

        store.connect("apply-failed", lambda _s, err: self.toast(f"Could not apply: {err[:120]}", 6))

        # Sidebar
        self.sidebar_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.sidebar_list.add_css_class("navigation-sidebar")
        for page_id, title, icon, _module in PAGES:
            box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
            box.append(Gtk.Image.new_from_icon_name(icon))
            box.append(Gtk.Label(label=title, xalign=0, hexpand=True))
            row = Gtk.ListBoxRow(child=box)
            row.page_id = page_id
            self.sidebar_list.append(row)
            self.rows[page_id] = row
        self.sidebar_list.connect("row-selected", self._on_row_selected)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Adw.WindowTitle(title="Lennox", subtitle=f"Settings · {VERSION}"))
        sidebar_view = Adw.ToolbarView()
        sidebar_view.add_top_bar(sidebar_header)
        sidebar_view.set_content(Gtk.ScrolledWindow(child=self.sidebar_list, hscrollbar_policy=Gtk.PolicyType.NEVER))
        sidebar_page = Adw.NavigationPage(title="Lennox", child=sidebar_view)

        # Content
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=150)
        self.content_title = Adw.WindowTitle(title="")
        content_header = Adw.HeaderBar()
        content_header.set_title_widget(self.content_title)
        content_view = Adw.ToolbarView()
        content_view.add_top_bar(content_header)
        self.toasts = Adw.ToastOverlay(child=self.stack)
        content_view.set_content(self.toasts)
        self.content_page = Adw.NavigationPage(title="", child=content_view)

        self.split = Adw.NavigationSplitView(sidebar=sidebar_page, content=self.content_page)
        self.split.set_min_sidebar_width(220)
        self.split.set_max_sidebar_width(280)
        self.set_content(self.split)

        # Narrow windows collapse the sidebar into a back button
        breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        breakpoint.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(breakpoint)

        # Escape closes the window, like the other Lennox popups
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self.connect("close-request", self._on_close)

    # ---------------------------------------------------------------- pages

    def show_page(self, page_id):
        if page_id not in self.rows:
            page_id = "welcome"
        row = self.rows[page_id]
        if self.sidebar_list.get_selected_row() is row:
            self._open(page_id)
        else:
            self.sidebar_list.select_row(row)
        self.split.set_show_content(True)

    def _on_row_selected(self, _list, row):
        if row is not None:
            self._open(row.page_id)
            self.split.set_show_content(True)

    def _open(self, page_id):
        title = next(t for i, t, _ic, _m in PAGES if i == page_id)
        page = self.pages.get(page_id)
        if page is None:
            module_name = next(m for i, _t, _ic, m in PAGES if i == page_id)
            try:
                module = importlib.import_module(f"lennox.app.pages.{module_name}")
                page = module.Page(self.ctx)
            except Exception as e:  # a broken page must not take the app down
                page = _ErrorPage(title, e)
            self.pages[page_id] = page
            self.stack.add_named(page.widget, page_id)
        self.stack.set_visible_child_name(page_id)
        self.content_title.set_title(title)
        self.content_page.set_title(title)
        refresh = getattr(page, "refresh", None)
        if refresh:
            refresh()

    # ---------------------------------------------------------------- misc

    def toast(self, text, timeout=3):
        toast = Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout)
        self.toasts.add_toast(toast)

    def _on_key(self, _controller, keyval, _keycode, state):
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape and not (state & Gdk.ModifierType.CONTROL_MASK):
            self.close()
            return True
        return False

    def _on_close(self, _window):
        self.store.flush_now()
        return False


class _ErrorPage:
    def __init__(self, title, error):
        self.widget = Adw.StatusPage(
            icon_name="dialog-error-symbolic",
            title=f"{title} could not open",
            description=f"{type(error).__name__}: {error}\n\nRun `lennox-settings` in a terminal to see details.",
        )
        print(f"lennox-settings: page {title} failed: {error!r}", file=sys.stderr)


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("page", ord("p"), GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "Open this page: " + ", ".join(PAGE_IDS), "NAME")
        self.window = None
        self.store = None

    def do_command_line(self, command_line):
        options = command_line.get_options_dict().end().unpack()
        page = options.get("page", "welcome")
        if self.window is None:
            self.store = Store()
            self.window = Window(self, self.store)
        else:
            self.store.reload()
        self.window.show_page(page)
        self.window.present()
        return 0


def main(argv=None):
    app = Application()
    return app.run(argv if argv is not None else sys.argv)
