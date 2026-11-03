"""Trophies: silly badges for using Lennox."""

import json

from gi.repository import Adw, Gtk

from ..util import lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = Adw.PreferencesPage()
        self.group = Adw.PreferencesGroup(title="Trophies", description="They unlock by themselves as you use Lennox.")
        self.page.add(self.group)
        self.items = []
        self.widget = self.page

    def refresh(self):
        run_async([lennox_bin("lennox-achieve"), "list"], self._got)

    def _got(self, ok, out, _err):
        try:
            trophies = json.loads(out) if ok else []
        except ValueError:
            trophies = []
        for row in self.items:
            self.group.remove(row)
        self.items = []
        done = sum(1 for t in trophies if t["done"])
        self.group.set_title(f"Trophies  ·  {done} of {len(trophies)}")
        for t in sorted(trophies, key=lambda t: not t["done"]):
            row = Adw.ActionRow(title=t["title"], subtitle=t["text"], use_markup=False)
            row.add_prefix(Gtk.Image.new_from_icon_name(t["icon"] if t["done"] else "changes-prevent-symbolic"))
            if t["done"]:
                row.add_suffix(Gtk.Label(label="Unlocked", css_classes=["success"]))
            else:
                row.add_suffix(Gtk.Label(label=f"{t['have']} / {t['goal']}", css_classes=["dim-label"]))
                row.set_sensitive(True)
                row.add_css_class("dim-label")
            self.group.add(row)
            self.items.append(row)
