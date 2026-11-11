"""Keybindings: a searchable list of every shortcut."""

import json

from gi.repository import Adw, Gtk

from ..util import run_async

MODS = [(64, "SUPER"), (4, "CTRL"), (8, "ALT"), (1, "SHIFT")]
PRETTY = {
    "mouse:272": "Left mouse", "mouse:273": "Right mouse", "mouse_down": "Scroll down", "mouse_up": "Scroll up",
    "RETURN": "Enter", "Return": "Enter", "SPACE": "Space", "ESCAPE": "Esc", "TAB": "Tab", "PRINT": "Print",
}


def describe(bind):
    mods = [name for bit, name in MODS if bind.get("modmask", 0) & bit]
    key = bind.get("key", "")
    return " + ".join(mods + [PRETTY.get(key, key)])


class Page:
    def __init__(self, ctx):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.search = Gtk.SearchEntry(placeholder_text="Search shortcuts (e.g. screenshot, workspace, volume)")
        self.search.connect("search-changed", lambda _e: self.list.invalidate_filter())
        box.append(self.search)

        hint = Gtk.Label(label="To change a shortcut, unbind and bind it again in ~/.config/hypr/custom.lua "
                               "(examples are at the top of ~/.config/hypr/lennox/keybinds.lua).",
                         wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.list.set_filter_func(self._filter)
        clamp = Adw.Clamp(maximum_size=900, child=self.list)
        box.append(clamp)

        self.widget = Gtk.ScrolledWindow(child=box, vexpand=True)
        self.loaded = False

    def _filter(self, row):
        text = self.search.get_text().strip().lower()
        return not text or text in row.search_text

    def refresh(self):
        if self.loaded:
            return

        def got(ok, out, _err):
            try:
                binds = json.loads(out) if ok else []
            except ValueError:
                binds = []
            seen = set()
            for bind in binds:
                description = bind.get("description") or ""
                if not description:
                    continue
                combo = describe(bind)
                if (combo, description) in seen:
                    continue
                seen.add((combo, description))
                row = Adw.ActionRow(title=description, use_markup=False)
                label = Gtk.Label(label=combo, valign=Gtk.Align.CENTER)
                label.add_css_class("monospace")
                label.add_css_class("dim-label")
                row.add_suffix(label)
                row.search_text = f"{description} {combo}".lower()
                self.list.append(row)
            if not seen:
                row = Adw.ActionRow(title="Shortcuts are listed while Hyprland is running")
                row.search_text = ""
                self.list.append(row)
            self.loaded = True

        run_async(["hyprctl", "binds", "-j"], got)
