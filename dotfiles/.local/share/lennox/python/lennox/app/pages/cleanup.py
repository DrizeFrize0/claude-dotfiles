"""Cleanup: see what's taking space for nothing, and free it with one button."""

import json
import os
import shutil
import time

from gi.repository import Adw, Gtk

from .. import rows
from ..util import lennox_bin, run_async
from ...cleanup import ITEMS, human, last_run


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.busy = False
        self.checks = {}
        self.rows = {}
        page = Adw.PreferencesPage()

        self.space = Adw.PreferencesGroup(
            title="Free up space",
            description="Only things that can be downloaded again, packages nothing uses, old logs, and "
                        "trash you threw away a while ago. Nothing you made is touched. The system parts "
                        "ask for your password once.")
        for item, (title, root) in ITEMS.items():
            row = Adw.ActionRow(title=title, subtitle="…")
            check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            size = Gtk.Label(css_classes=["dim-label"], valign=Gtk.Align.CENTER)
            row.add_suffix(size)
            row.size_label = size
            self.checks[item] = check
            self.rows[item] = row
            self.space.add(row)
        self.total = Adw.ActionRow(title="Total", subtitle="Checking…")
        self.button = Gtk.Button(label="Clean now", valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
        self.button.connect("clicked", lambda _b: self._clean())
        self.spinner = Gtk.Spinner(valign=Gtk.Align.CENTER)
        self.total.add_suffix(self.spinner)
        self.total.add_suffix(self.button)
        self.space.add(self.total)
        page.add(self.space)

        auto = Adw.PreferencesGroup(
            title="Automatic",
            description="Once a week, quietly: old trash, old thumbnails and AUR build files (no password "
                        "needed). Old package downloads are also trimmed by the automatic updates.")
        auto.add(rows.switch_row(ctx.store, "cleanup.weekly", "Clean up every week"))
        auto.add(rows.spin_row(ctx.store, "cleanup.trash_days", "Empty trash older than",
                               "Days (0 empties all of it)", lower=0, upper=365, step=1))
        self.last_row = rows.info_row("Last cleanup", "Never")
        auto.add(self.last_row)
        self.disk_row = rows.info_row("Free space", "")
        auto.add(self.disk_row)
        page.add(auto)
        self.widget = page

    def refresh(self):
        if self.busy:
            return
        self._show_last()
        self.total.set_subtitle("Checking…")
        self.spinner.start()
        run_async([lennox_bin("lennox-cleanup"), "scan", "--json"], self._got_scan)

    def _show_last(self):
        last = last_run()
        if last:
            when = time.strftime("%-d %b, %H:%M", time.localtime(last.get("time", 0)))
            how = "weekly" if last.get("auto") else "by hand"
            self.last_row.value_label.set_label(f"{when} ({how}): freed {human(last.get('freed', 0))}")
        free = shutil.disk_usage(os.path.expanduser("~")).free
        self.disk_row.value_label.set_label(f"{human(free)} free")

    def _got_scan(self, ok, out, err):
        self.spinner.stop()
        try:
            items = json.loads(out) if ok else None
        except ValueError:
            items = None
        if not isinstance(items, list):
            self.total.set_subtitle("Couldn't check: " + (err.strip().splitlines() or ["unknown error"])[-1])
            return
        total = 0
        for it in items:
            row = self.rows.get(it.get("id"))
            if row is None:
                continue
            row.set_subtitle(it.get("detail", ""))
            row.size_label.set_label(it.get("size", ""))
            total += it.get("bytes", 0)
        self.total.set_subtitle(f"About {human(total)} can be freed" if total else "Already clean")

    def _clean(self):
        ids = [item for item, check in self.checks.items() if check.get_active()]
        if not ids:
            self.ctx.toast("Tick at least one thing to clean")
            return
        self.busy = True
        self.button.set_sensitive(False)
        self.spinner.start()
        self.total.set_subtitle("Cleaning…")

        def done(ok, out, err):
            self.busy = False
            self.button.set_sensitive(True)
            self.spinner.stop()
            message = out.strip().splitlines()[-1] if ok and out.strip() else "Cleanup failed: " + err.strip()[-200:]
            self.ctx.toast(message, timeout=5)
            self.refresh()

        run_async([lennox_bin("lennox-cleanup"), "now", *ids], done)
