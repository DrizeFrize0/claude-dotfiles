"""Health Check: runs `lennox-doctor` and shows what to fix."""

import json

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async

ICONS = {"ok": "emblem-ok-symbolic", "warn": "dialog-warning-symbolic", "fail": "dialog-error-symbolic"}
SECTIONS = {"graphics": "Graphics", "audio": "Sound and microphone", "input": "Keyboard and touchpad",
            "net": "Network and Bluetooth", "updates": "Updates and safety", "desktop": "Desktop"}


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.page = Adw.PreferencesPage()
        top = Adw.PreferencesGroup(description="Checks drivers (NVIDIA, Intel, sound and mic firmware), the touchpad, "
                                               "network, updates and the desktop. Every problem comes with a fix.")
        self.run_row = rows.button_row("Health check", "Takes a few seconds", "Run", self.run,
                                       "emblem-ok-symbolic", suggested=True)
        top.add(self.run_row)
        self.page.add(top)
        self.groups = []
        self.widget = self.page
        self.ran = False

    def refresh(self):
        if not self.ran:
            self.run()

    def run(self):
        self.ran = True
        self.run_row.set_subtitle("Checking…")

        def done(_ok, out, err):
            for group in self.groups:
                self.page.remove(group)
            self.groups = []
            try:
                report = json.loads(out)
            except ValueError:
                self.run_row.set_subtitle(f"Could not run the check: {err.strip()[-120:]}")
                return
            failures, warnings = report.get("failures", 0), report.get("warnings", 0)
            if failures == 0 and warnings == 0:
                self.run_row.set_subtitle("All good ✓")
            else:
                self.run_row.set_subtitle(f"{failures} problem(s), {warnings} warning(s)")
            by_section = {}
            for check in report.get("checks", []):
                by_section.setdefault(check.get("section"), []).append(check)
            for section, checks in by_section.items():
                group = Adw.PreferencesGroup(title=GLib.markup_escape_text(SECTIONS.get(section, section or "Other")))
                for check in checks:
                    # Messages contain device names: show them as plain text, not markup
                    row = Adw.ActionRow(title=check.get("message", ""), use_markup=False)
                    level = check.get("level", "ok")
                    if level != "ok" and check.get("hint"):
                        row.set_subtitle(check["hint"])
                        row.set_subtitle_selectable(True)
                    icon = Gtk.Image.new_from_icon_name(ICONS.get(level, ICONS["ok"]))
                    icon.add_css_class({"ok": "success", "warn": "warning", "fail": "error"}.get(level, ""))
                    row.add_prefix(icon)
                    group.add(row)
                self.page.add(group)
                self.groups.append(group)

        run_async([lennox_bin("lennox-doctor"), "--json"], done)
