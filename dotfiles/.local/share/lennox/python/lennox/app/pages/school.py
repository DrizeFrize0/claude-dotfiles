"""School: deadlines, quiet hours during school, a quick focus start."""

import json

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        self.list_group = Adw.PreferencesGroup(title="Deadlines", description="Reminders come a day and two hours before.")
        self.list_rows = []
        page.add(self.list_group)

        add = Adw.PreferencesGroup(title="Add a deadline")
        self.title_row = Adw.EntryRow(title="What is due (for example: Chemistry report)")
        self.date_row = Adw.EntryRow(title="When: tomorrow, sun, +3, or 2026-11-20 (add a time: 2026-11-20 14:00)")
        add.add(self.title_row)
        add.add(self.date_row)
        add.add(rows.button_row("Add", "", "Add", self._add, "list-add-symbolic", suggested=True))
        page.add(add)

        quiet = Adw.PreferencesGroup(
            title="Quiet hours",
            description="Notifications wait in the panel during school (Do not disturb). School days default to Sunday to Thursday.")
        quiet.add(rows.switch_row(store, "school.schedule", "Quiet during school hours"))
        quiet.add(rows.entry_row(store, "school.days", "School days (sun, mon, tue, wed, thu)"))
        quiet.add(rows.time_row(store, "school.from", "School starts"))
        quiet.add(rows.time_row(store, "school.to", "School ends"))
        quiet.add(rows.switch_row(store, "school.remind", "Remind me before a deadline"))
        quiet.add(rows.button_row("Quiet for an hour", "Right now", "Start", lambda: self._cmd("quiet", "for", "60"), "notifications-disabled-symbolic"))
        quiet.add(rows.button_row("Notifications back", "End quiet time", "Stop", lambda: self._cmd("quiet", "off"), "preferences-system-notifications-symbolic"))
        page.add(quiet)

        study = Adw.PreferencesGroup(title="Study", description="Focus sessions, Pomodoro rounds and subjects live on the Focus page (SUPER + F12 starts one).")
        page.add(study)
        self.widget = page

    def _cmd(self, *args, then=None):
        def done(ok, out, err):
            if not ok:
                self.ctx.toast((err or out).strip().splitlines()[-1] if (err or out).strip() else "That did not work")
            if then:
                then()
        run_async([lennox_bin("lennox-school"), *args], done)

    def _add(self):
        title, when = self.title_row.get_text().strip(), self.date_row.get_text().strip()
        if not title or not when:
            self.ctx.toast("Write what is due and when")
            return
        words = when.split()
        self._cmd("add", title, *words[:2], then=self.refresh)
        self.title_row.set_text("")
        self.date_row.set_text("")

    def refresh(self):
        run_async([lennox_bin("lennox-school"), "list", "--json"], self._got)

    def _got(self, ok, out, _err):
        for row in self.list_rows:
            self.list_group.remove(row)
        self.list_rows = []
        try:
            items = json.loads(out) if ok else []
        except ValueError:
            items = []
        if not items:
            row = Adw.ActionRow(title="Nothing due 🎉")
            self.list_group.add(row)
            self.list_rows.append(row)
            return
        for d in items:
            row = Adw.ActionRow(title=GLib.markup_escape_text(d["title"]), subtitle=d.get("when", ""))
            button = Gtk.Button(label="Done", valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda _b, i=d["id"]: self._cmd("done", str(i), then=self.refresh))
            row.add_suffix(button)
            self.list_group.add(row)
            self.list_rows.append(row)
