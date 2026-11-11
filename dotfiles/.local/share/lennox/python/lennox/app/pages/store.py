"""App store: one search over Arch, the AUR and Flathub; install, update, remove."""

import json
import os

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async

BADGES = {"arch": "Arch", "aur": "AUR", "flathub": "Flathub"}
ICON_DIRS = ["/var/lib/flatpak/appstream/flathub/x86_64/active/icons/64x64",
             os.path.expanduser("~/.local/share/flatpak/appstream/flathub/x86_64/active/icons/64x64")]
WHERE = {"flathub": "Flathub: sandboxed app, works on any Linux, updates by itself",
         "arch": "Arch: from the official Arch repositories",
         "aur": "AUR: made by the community, built on your PC"}


def _icon(app):
    if app["source"] == "flathub":
        for folder in ICON_DIRS:
            path = os.path.join(folder, app["id"] + ".png")
            if os.path.exists(path):
                image = Gtk.Image.new_from_file(path)
                image.set_pixel_size(32)
                return image
    image = Gtk.Image.new_from_icon_name("application-x-executable-symbolic"
                                         if app["source"] == "flathub" else "package-x-generic-symbolic")
    image.set_pixel_size(24)
    return image


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.query = ""
        self.busy = False
        self.generation = 0
        page = Adw.PreferencesPage()

        top = Adw.PreferencesGroup(
            title="App Store",
            description="Arch, the AUR and Flathub in one search. Installing opens a small window where "
                        "you type your password and can watch it work.")
        self.entry = Gtk.SearchEntry(placeholder_text="Search apps: discord, obs, spotify, minecraft…",
                                     hexpand=True)
        self.entry.connect("activate", lambda _e: self._search(self.entry.get_text()))
        self.entry.connect("search-changed", self._typed)
        self.spinner = Gtk.Spinner()
        top.set_header_suffix(self.spinner)
        top.add(self.entry)
        page.add(top)

        self.results = Adw.PreferencesGroup()
        page.add(self.results)
        self.result_rows = []

        everything = Adw.PreferencesGroup(title="Updates")
        everything.add(rows.button_row("Update everything", "System, drivers, AUR apps and Flatpaks",
                                       "Update", lambda: run_async([lennox_bin("lennox-update")]),
                                       "software-update-available-symbolic"))
        page.add(everything)
        self.page = page
        self.widget = page
        self.timer = None

    def refresh(self):
        if not self.query:
            self._load_installed()

    # ------------------------------------------------------------ results

    def _clear(self):
        for row in self.result_rows:
            self.results.remove(row)
        self.result_rows = []

    def _show(self, apps, title, empty):
        self._clear()
        self.results.set_title(title)
        if not apps:
            row = Adw.ActionRow(title=empty)
            self.results.add(row)
            self.result_rows.append(row)
            return
        for app in apps:
            row = Adw.ActionRow(title=GLib.markup_escape_text(app["name"]),
                                subtitle=GLib.markup_escape_text(app.get("description") or app["id"]),
                                subtitle_lines=2, tooltip_text=WHERE.get(app["source"], ""))
            row.add_prefix(_icon(app))
            badge = Gtk.Label(label=BADGES.get(app["source"], app["source"]), valign=Gtk.Align.CENTER,
                              css_classes=["dim-label", "caption"])
            row.add_suffix(badge)
            if app.get("update"):
                row.add_suffix(self._button("Update", "update", app, ["suggested-action"]))
            if app.get("installed"):
                row.add_suffix(self._button("Remove", "remove", app, []))
            else:
                row.add_suffix(self._button("Install", "install", app, ["suggested-action"]))
            self.results.add(row)
            self.result_rows.append(row)

    def _button(self, label, action, app, classes):
        button = Gtk.Button(label=label, valign=Gtk.Align.CENTER, css_classes=classes)
        button.connect("clicked", lambda _b: self._do(action, app))
        return button

    def _load_installed(self):
        generation = self._start()

        def got(ok, out, _err):
            if generation != self.generation:
                return
            self.spinner.stop()
            try:
                apps = json.loads(out) if ok else []
            except ValueError:
                apps = []
            self._show(apps, "Apps you added", "Search above to find apps")

        run_async([lennox_bin("lennox-apps"), "installed"], got)

    def _start(self):
        self.generation += 1
        self.spinner.start()
        return self.generation

    # ------------------------------------------------------------ searching

    def _typed(self, entry):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(600, self._typed_done)

    def _typed_done(self):
        self.timer = None
        self._search(self.entry.get_text())
        return False

    def _search(self, text):
        self.query = text.strip()
        if not self.query:
            self._load_installed()
            return
        if len(self.query) < 2:
            return
        generation = self._start()
        self.results.set_title(f"Searching for “{self.query}”…")

        def got(ok, out, err):
            if generation != self.generation:
                return                       # a newer search is on its way
            self.spinner.stop()
            try:
                apps = json.loads(out) if ok else None
            except ValueError:
                apps = None
            if apps is None:
                self._show([], "Search failed", err.strip()[-200:] or "Search failed")
            else:
                self._show(apps, f"Results for “{self.query}”", "Nothing found. Try another word.")

        run_async([lennox_bin("lennox-apps"), "search", *self.query.split()], got)

    # ------------------------------------------------------------ install / update / remove

    def _do(self, action, app):
        if self.busy:
            self.ctx.toast("One at a time: finish the open install window first")
            return
        self.busy = True
        verb = {"install": "Installing", "update": "Updating", "remove": "Removing"}[action]
        self.ctx.toast(f"{verb} {app['name']}… (see the small window)")

        def done(ok, _out, _err):
            self.busy = False
            past = {"install": "installed", "update": "updated", "remove": "removed"}[action]
            self.ctx.toast(f"{app['name']} {past}" if ok else f"{app['name']} was not {past}")
            if self.query:
                self._search(self.query)
            else:
                self._load_installed()

        run_async([lennox_bin("lennox-apps"), action, app["source"], app["id"]], done)
