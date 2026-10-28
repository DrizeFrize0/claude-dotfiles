"""Welcome: first steps and the shortcuts worth knowing."""

import os

from gi.repository import Adw, Gtk

from .. import rows
from ..util import ASSETS, launch, lennox_bin

ESSENTIAL_KEYS = [
    ("SUPER + SPACE", "Apps"),
    ("SUPER + RETURN", "Terminal"),
    ("SUPER + B / E", "Browser / Files"),
    ("SUPER + N", "Quick panel"),
    ("SUPER + I", "Lennox Settings"),
    ("SUPER + W", "Pick a wallpaper"),
    ("SUPER + Q", "Close a window"),
    ("SUPER + 1 … 0", "Workspaces (or swipe 3 fingers)"),
    ("SUPER + V", "Clipboard history"),
    ("PRINT", "Screenshot an area"),
    ("SUPER + L", "Lock"),
    ("SUPER + CTRL + K", "Every shortcut"),
]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        page = Adw.PreferencesPage()

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12, margin_bottom=6)
        logo = os.path.join(ASSETS, "lennox.svg")
        if os.path.exists(logo):
            picture = Gtk.Picture.new_for_filename(logo)
            picture.set_size_request(72, 72)
            picture.set_can_shrink(True)
            picture.set_halign(Gtk.Align.CENTER)
            picture.add_css_class("lennox-logo")
            hero.append(picture)
        title = Gtk.Label(label=f"Welcome, {os.environ.get('USER', 'friend')}")
        title.add_css_class("title-1")
        hero.append(title)
        subtitle = Gtk.Label(
            label="Your desktop, your rules. Everything here applies instantly,\n"
                  "and every color follows your wallpaper.",
            justify=Gtk.Justification.CENTER)
        subtitle.add_css_class("dim-label")
        hero.append(subtitle)
        hero_group = Adw.PreferencesGroup()
        hero_group.add(hero)
        page.add(hero_group)

        start = Adw.PreferencesGroup(title="Make it yours")
        start.add(rows.link_row("Pick a wallpaper", "The whole desktop re-colors to match it",
                                lambda: ctx.navigate("wallpaper"), "preferences-desktop-wallpaper-symbolic"))
        start.add(rows.link_row("Change the look", "Dark or light, animations, gaps, blur, rounded corners",
                                lambda: ctx.navigate("appearance"), "applications-graphics-symbolic"))
        start.add(rows.link_row("Bar style", "Lennox Islands or Line, or the classic ML4W bars",
                                lambda: ctx.navigate("bar"), "view-grid-symbolic"))
        start.add(rows.link_row("Widgets and dashboard", "Clock, weather and music on your desktop; SUPER + D for the dashboard",
                                lambda: ctx.navigate("widgets"), "view-app-grid-symbolic"))
        start.add(rows.link_row("Check drivers, sound and mic", "One click health check",
                                lambda: ctx.navigate("health"), "emblem-ok-symbolic"))
        page.add(start)

        keys = Adw.PreferencesGroup(title="Shortcuts worth knowing",
                                    description="SUPER is the Windows key.")
        for combo, action in ESSENTIAL_KEYS:
            row = Adw.ActionRow(title=action)
            label = Gtk.Label(label=combo, valign=Gtk.Align.CENTER)
            label.add_css_class("monospace")
            label.add_css_class("dim-label")
            row.add_suffix(label)
            keys.add(row)
        keys.add(rows.link_row("See every shortcut", "Searchable list", lambda: ctx.navigate("keybinds"),
                               "preferences-desktop-keyboard-shortcuts-symbolic"))
        page.add(keys)

        more = Adw.PreferencesGroup()
        more.add(rows.switch_row(ctx.store, "welcome.show_on_login", "Show this page when I log in"))
        more.add(rows.button_row("Open a terminal", "Type `lennox` for the command line tools", "Open",
                                 lambda: launch([lennox_bin("lennox-open"), "terminal"]), "utilities-terminal-symbolic"))
        page.add(more)
        self.widget = page
