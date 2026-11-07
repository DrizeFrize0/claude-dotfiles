"""About Lennox."""

import os
import platform

from gi.repository import Adw, GLib, Gtk

from ... import VERSION, whatsnew
from .. import rows
from ..util import ASSETS, HOME, launch, read_file, run_async


class Page:
    def __init__(self, ctx):
        page = Adw.PreferencesPage()

        hero = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12)
        logo = os.path.join(ASSETS, "lennox.svg")
        if os.path.exists(logo):
            picture = Gtk.Picture.new_for_filename(logo)
            picture.set_size_request(64, 64)
            picture.set_halign(Gtk.Align.CENTER)
            box.append(picture)
        title = Gtk.Label(label="Lennox")
        title.add_css_class("title-1")
        box.append(title)
        version = read_file(os.path.join(HOME, ".config", "lennox", "version")).strip() or VERSION
        sub = Gtk.Label(label=f"Version {version} · Hyprland for Arch, in the spirit of ML4W")
        sub.add_css_class("dim-label")
        box.append(sub)
        hero.add(box)
        page.add(hero)

        # What's new: the latest version open, older ones folded away
        entries = whatsnew.load()
        if entries:
            latest = entries[0]
            news = Adw.PreferencesGroup(
                title=f"What's new in {latest['version']}",
                description=" · ".join(x for x in (latest["title"], latest["date"]) if x))
            for item in latest["items"]:
                row = Adw.ActionRow(title=GLib.markup_escape_text(item), title_lines=3)
                row.add_prefix(Gtk.Image.new_from_icon_name("starred-symbolic"))
                news.add(row)
            for entry in entries[1:]:
                older = Adw.ExpanderRow(title=f"Lennox {entry['version']}",
                                        subtitle=" · ".join(x for x in (entry["title"], entry["date"]) if x))
                for item in entry["items"]:
                    older.add_row(Adw.ActionRow(title=GLib.markup_escape_text(item), title_lines=3))
                news.add(older)
            page.add(news)
            whatsnew.mark_seen()            # read here, so no notification for it later

        system = Adw.PreferencesGroup(title="This computer")
        self.hyprland_row = rows.info_row("Hyprland", "…")
        system.add(self.hyprland_row)
        system.add(rows.info_row("Kernel", platform.release()))
        system.add(rows.info_row("Lennox files", os.path.join(HOME, ".config", "lennox")))
        repo = read_file(os.path.join(HOME, ".config", "lennox", "repo")).strip()
        if repo:
            system.add(rows.info_row("Installed from", repo))
        page.add(system)

        credits = Adw.PreferencesGroup(
            title="Credits",
            description="Lennox is built on the ideas, layout, lock screen, login theme and wallpapers of ML4W OS "
                        "by Stephan Raabe (mylinuxforwork). Like ML4W it is free software under the GPL-3.0 license.")
        credits.add(rows.link_row("ML4W OS", "ml4w.com/os", lambda: launch(["xdg-open", "https://ml4w.com/os/"]),
                                  "web-browser-symbolic"))
        credits.add(rows.link_row("Hyprland wiki", "wiki.hypr.land",
                                  lambda: launch(["xdg-open", "https://wiki.hypr.land/"]), "help-browser-symbolic"))
        credits.add(rows.link_row("Arch Wiki", "wiki.archlinux.org",
                                  lambda: launch(["xdg-open", "https://wiki.archlinux.org/"]), "help-browser-symbolic"))
        page.add(credits)
        self.widget = page

    def refresh(self):
        def got(ok, out, _err):
            first = out.strip().splitlines()[0] if ok and out.strip() else "not running"
            self.hyprland_row.value_label.set_label(first)

        run_async(["hyprctl", "version"], got)
