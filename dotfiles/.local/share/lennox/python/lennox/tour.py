"""The Lennox tour: a few friendly pages the first time you log in, and "What's new" after every upgrade.

    lennox-tour            open it from the start
    lennox-tour first      open it once (the first time); exits 10 without showing anything if you have seen it
    lennox-tour whatsnew   open it on the What's new page

Arrow keys or the buttons move between pages, Esc closes. Each page can open the matching Settings page.
"""

import os
import sys

from . import VERSION
from . import profile as P
from . import settings as S
from . import whatsnew as W

DONE = os.path.join(S.STATE_DIR, "tour_done")
SHOWN_BEFORE = 10


def tips(*pairs):
    return [{"keys": k, "what": w} for k, w in pairs]


def short(text, limit=110):
    """The first sentence of a changelog item, cut at a word if it is still long."""
    first = text.split(". ")[0].rstrip(".")
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0] + "…"


def pages(entries, name="there", since=None):
    """The tour pages as data: [{id, icon, title, body, tips, action}]. entries: the changelog (newest first);
    since: the version last seen (None = the latest release only)."""
    fresh = W.newer_than(entries, since) if entries else []
    news = []
    for e in fresh:
        news.append({"keys": f"Lennox {e['version']}", "what": e["title"] or ""})
        news += [{"keys": "•", "what": short(item)} for item in e["items"][:4]]
    return [
        {"id": "welcome", "icon": "weather-clear-symbolic", "title": f"Welcome, {name}",
         "body": "Lennox is your desktop: fast, pretty and made to look after itself. This takes one minute.",
         "tips": tips(("SUPER + SPACE", "Open an app"), ("SUPER + RETURN", "Open a terminal"), ("SUPER + Q", "Close a window")),
         "action": None},
        {"id": "find", "icon": "system-search-symbolic", "title": "Find anything",
         "body": "One search box does it all: settings, bar styles, fans, sounds, themes, tools.",
         "tips": tips(("SUPER + /", "Search everything"), ("SUPER + I", "Lennox Settings"), ("SUPER + N", "Quick panel")),
         "action": ("Open the search", "lennox-palette")},
        {"id": "yours", "icon": "applications-graphics-symbolic", "title": "Make it yours",
         "body": "Pick a picture and a name, a bar style, a wallpaper. Colors follow your wallpaper or a theme you choose.",
         "tips": tips(("SUPER + W", "Pick a wallpaper"), ("Settings > Profile", "Your name and picture"),
                      ("Settings > Bar", "13 bar styles")),
         "action": ("Open Profile", "lennox-settings --page profile")},
        {"id": "safe", "icon": "security-high-symbolic", "title": "Safe by design",
         "body": "Every update takes a restore point first, and Lennox watches for blocked sites and full disks. "
                 "If something breaks, you can go back.",
         "tips": tips(("lennox-heal fix", "Fix what is broken"), ("lennox-safety undo", "Take back the last update"),
                      ("lennox-safety files", "Copy your files to a drive"),
                      ("Boot menu", "Arch Linux snapshots start from a restore point")),
         "action": ("Check my health", "kitty --hold lennox-doctor")},
        {"id": "school", "icon": "alarm-symbolic", "title": "School and focus",
         "body": "Focus mode blocks the distractions and times your sessions. Deadlines remind you a day and two hours "
                 "before, and quiet hours keep notifications out of class.",
         "tips": tips(("SUPER + F12", "Start a focus session"), ("lennox-school add \"Essay\" sun", "Add a deadline"),
                      ("Settings > School", "Quiet during school hours")),
         "action": ("Open Focus", "lennox-settings --page focus")},
        {"id": "play", "icon": "input-gaming-symbolic", "title": "Games and battery",
         "body": "Games get their own mode automatically. Pin an app to the GTX 1650, and set a charge limit so the "
                 "battery lasts for years.",
         "tips": tips(("SUPER + ALT + G", "Game mode"), ("lennox-gpu pin blender", "Always use the NVIDIA GPU"),
                      ("lennox-laptop limit 80", "Charge only to 80%")),
         "action": ("Open Power", "lennox-settings --page power")},
        {"id": "news", "icon": "software-update-available-symbolic", "title": f"What's new in {VERSION}",
         "body": "Everything that changed since you last looked." if news else "You are up to date.",
         "tips": news, "action": ("Open the full list", "lennox-settings --page about")},
    ]


def seen_tour(path=DONE):
    return os.path.exists(path)


def mark_done(path=DONE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(VERSION + "\n")


CSS = """
window.lennox-tour {{ background: {surface}; color: {on_surface}; }}
.tour-badge {{ background: {primary_container}; color: {on_primary_container}; border-radius: 999px; padding: 22px; }}
.tour-title {{ font-size: 30px; font-weight: 800; }}
.tour-body {{ font-size: 15px; color: {on_surface_variant}; }}
.tour-keys {{ font-family: monospace; font-weight: 700; color: {primary}; }}
.tour-what {{ color: {on_surface}; }}
.tour-tips {{ background: {surface_container}; border-radius: 22px; padding: 16px 20px; }}
.tour-dot {{ min-width: 8px; min-height: 8px; border-radius: 999px; background: {outline_variant};
             transition: all 240ms cubic-bezier(0.05, 0.7, 0.1, 1); }}
.tour-dot.on {{ min-width: 26px; background: {primary}; }}
button.tour-next {{ background: {primary}; color: {on_primary}; border-radius: 999px; padding: 8px 26px; font-weight: 700; }}
button.tour-back, button.tour-action {{ border-radius: 999px; padding: 8px 22px; }}
"""


def run_window(start_at=0, dry=False):
    """Builds and shows the window (GTK is loaded here so the page data above stays importable without it)."""
    from . import overlay as O
    from .widgets.style import load_colors
    Gtk, GLib, Gdk = O.Gtk, O.GLib, O.Gdk

    class Tour(Gtk.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title="Welcome to Lennox", default_width=760, default_height=580,
                             resizable=False)
            self.add_css_class("lennox-tour")
            O.css(CSS.format(**load_colors()))
            self.entries = W.load()
            self.pages = pages(self.entries, P.display_name(), W.read_seen() or None)
            self.index = min(max(start_at, 0), len(self.pages) - 1)
            self.dry = dry
            self.launched = []

            self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=380,
                                   hexpand=True, vexpand=True)
            for page in self.pages:
                self.stack.add_named(self._build(page), page["id"])
            self.dots = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            self.dot_list = []
            for _ in self.pages:
                dot = Gtk.Box(css_classes=["tour-dot"])
                self.dots.append(dot)
                self.dot_list.append(dot)
            self.back = Gtk.Button(label="Back", css_classes=["tour-back", "flat"])
            self.next = Gtk.Button(css_classes=["tour-next"])
            self.back.connect("clicked", lambda _b: self.go(-1))
            self.next.connect("clicked", lambda _b: self.go(1))
            bottom = Gtk.CenterBox(margin_start=28, margin_end=28, margin_bottom=22)
            bottom.set_start_widget(self.back)
            bottom.set_center_widget(self.dots)
            bottom.set_end_widget(self.next)
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            column.append(self.stack)
            column.append(bottom)
            self.set_child(column)
            keys = Gtk.EventControllerKey()
            keys.connect("key-pressed", self._key)
            self.add_controller(keys)
            self.connect("close-request", self._closing)
            self.show_page(self.index, animate=False)

        def _build(self, page):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER,
                          valign=Gtk.Align.CENTER, margin_top=30, margin_start=40, margin_end=40)
            box.append(self._badge(page["icon"]))
            box.append(Gtk.Label(label=page["title"], css_classes=["tour-title"]))
            box.append(Gtk.Label(label=page["body"], css_classes=["tour-body"], wrap=True, justify=Gtk.Justification.CENTER,
                                 max_width_chars=60))
            if page["tips"]:
                grid = Gtk.Grid(column_spacing=18, row_spacing=7, css_classes=["tour-tips"], halign=Gtk.Align.CENTER)
                for row, tip in enumerate(page["tips"]):
                    grid.attach(Gtk.Label(label=tip["keys"], xalign=0, css_classes=["tour-keys"]), 0, row, 1, 1)
                    grid.attach(Gtk.Label(label=tip["what"], xalign=0, wrap=True, max_width_chars=46,
                                          css_classes=["tour-what"]), 1, row, 1, 1)
                box.append(grid)
            if page["action"]:
                label, command = page["action"]
                button = Gtk.Button(label=label, css_classes=["tour-action"], halign=Gtk.Align.CENTER)
                button.connect("clicked", lambda _b, c=command: self.launch(c))
                box.append(button)
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, hexpand=True)
            scroller.set_child(box)
            return scroller

        def _badge(self, icon):
            frame = Gtk.Box(css_classes=["tour-badge"], halign=Gtk.Align.CENTER)
            frame.append(Gtk.Image(icon_name=icon, pixel_size=44))
            return frame

        def launch(self, command):
            self.launched.append(command)
            if self.dry:
                return
            env_path = os.path.join(os.path.expanduser("~"), ".local", "bin") + os.pathsep + os.environ.get("PATH", "")
            try:
                GLib.spawn_async(["env", f"PATH={env_path}", "sh", "-c", command], flags=GLib.SpawnFlags.SEARCH_PATH)
            except GLib.Error:
                pass

        def show_page(self, index, animate=True):
            self.index = index
            if not animate:
                self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
            else:
                self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
            self.stack.set_visible_child_name(self.pages[index]["id"])
            for i, dot in enumerate(self.dot_list):
                (dot.add_css_class if i == index else dot.remove_css_class)("on")
            self.back.set_visible(index > 0)
            self.next.set_label("Done" if index == len(self.pages) - 1 else "Next")

        def go(self, step):
            target = self.index + step
            if target >= len(self.pages):
                self.close()
            elif target >= 0:
                self.show_page(target)

        def _key(self, _c, keyval, _code, _state):
            name = (Gdk.keyval_name(keyval) or "").lower()
            if name == "escape":
                self.close()
            elif name in ("right", "return", "space"):
                self.go(1)
            elif name == "left":
                self.go(-1)
            else:
                return False
            return True

        def _closing(self, _w):
            if not self.dry:
                mark_done()
                W.mark_seen()
            return False

    app = Gtk.Application(application_id="dev.lennox.Tour")
    holder = {}

    def activate(a):
        holder["win"] = Tour(a)
        holder["win"].present()

    app.connect("activate", activate)
    return app, holder


def main(argv):
    mode = argv[1] if len(argv) > 1 else "show"
    if mode == "first" and seen_tour():
        return SHOWN_BEFORE
    if mode not in ("show", "first", "whatsnew"):
        print("usage: lennox-tour [first|whatsnew]", file=sys.stderr)
        return 2
    start = 0
    if mode == "whatsnew":
        start = 10 ** 6                       # clamped to the last page
    app, _holder = run_window(start)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
