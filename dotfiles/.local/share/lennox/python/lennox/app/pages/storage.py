"""Storage: what is using the disk, biggest first, with a safe delete (to the trash) and Open in Files."""

import json
import os

from gi.repository import Adw, Gtk

from ... import storage as ST
from .. import rows
from ..util import lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.folder = ST.HOME
        self.page = Adw.PreferencesPage()
        self.summary = Adw.PreferencesGroup(title="Disk")
        self.space_row = rows.info_row("Free space", "…")
        self.bar = Gtk.LevelBar(min_value=0, max_value=1, value=0, margin_top=6, margin_bottom=6, hexpand=True)
        self.summary.add(self.space_row)
        self.summary.add(self.bar)
        self.page.add(self.summary)
        self.group = Adw.PreferencesGroup(title="Biggest first")
        self.nav = rows.button_row("Folder", ST.HOME, "Up", self._up, icon="go-up-symbolic")
        self.group.add(self.nav)
        self.page.add(self.group)
        self.items = []
        self.widget = self.page
        self.busy = False

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.nav.set_subtitle(self.folder)
        run_async([lennox_bin("lennox-storage"), "scan", self.folder], self._got)

    def _up(self):
        parent = os.path.dirname(self.folder)
        if parent.startswith(ST.HOME) and parent != self.folder:
            self.folder = parent
            self.refresh()

    def _got(self, ok, out, _err):
        self.busy = False
        try:
            data = json.loads(out) if ok else None
        except ValueError:
            data = None
        if not data:
            return
        self.space_row.value_label.set_label(f"{ST.human(data['free'])} free of {ST.human(data['total'])}")
        self.bar.set_value(data["used"] / max(data["total"], 1))
        for row in self.items:
            self.group.remove(row)
        self.items = []
        biggest = max([i["size"] for i in data["items"]] + [1])
        for item in data["items"]:
            row = Adw.ActionRow(title=item["name"], use_markup=False)
            row.set_subtitle(ST.human(item["size"]))
            share = Gtk.LevelBar(min_value=0, max_value=1, value=item["size"] / biggest, width_request=120, valign=Gtk.Align.CENTER)
            row.add_suffix(share)
            if item["dir"]:
                enter = Gtk.Button(icon_name="go-next-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Look inside")
                enter.add_css_class("flat")
                enter.connect("clicked", lambda _b, p=item["path"]: self._enter(p))
                row.add_suffix(enter)
            show = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Open in Files")
            show.add_css_class("flat")
            show.connect("clicked", lambda _b, p=item["path"]: run_async([lennox_bin("lennox-storage"), "open", p]))
            row.add_suffix(show)
            if item["safe"]:
                trash = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Move to the trash")
                trash.add_css_class("flat")
                trash.connect("clicked", lambda _b, i=item: self._confirm(i))
                row.add_suffix(trash)
            self.group.add(row)
            self.items.append(row)

    def _enter(self, path):
        self.folder = path
        self.refresh()

    def _confirm(self, item):
        dialog = Adw.AlertDialog(heading=f"Move {item['name']} to the trash?",
                                 body=f"That frees {ST.human(item['size'])}. It stays in the trash until you empty it, "
                                      "so you can still get it back.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("trash", "Move to the trash")
        dialog.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def chosen(_d, response):
            if response == "trash":
                def done(ok, _o, err):
                    self.ctx.toast("Moved to the trash" if ok else (err.strip() or "Couldn't move it"))
                    self.refresh()
                run_async([lennox_bin("lennox-storage"), "trash", item["path"]], done)
        dialog.connect("response", chosen)
        dialog.present(self.ctx.window)
