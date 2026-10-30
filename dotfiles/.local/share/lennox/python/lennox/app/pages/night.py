"""Night: night light, sleep wind-down and sleep stats."""

import datetime
import json

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        store = ctx.store
        page = Adw.PreferencesPage()

        light = Adw.PreferencesGroup(title="Night light",
                                     description="Warmer screen colors in the evening: easier on the eyes and on falling "
                                                 "asleep. Screenshots and recordings are not affected.")
        light.add(rows.switch_row(store, "night.nightlight", "Turn on automatically"))
        light.add(rows.time_row(store, "night.start", "From"))
        light.add(rows.time_row(store, "night.end", "Until"))
        light.add(rows.spin_row(store, "night.temperature", "Warmth", "Lower = warmer (Kelvin)",
                                lower=2500, upper=6000, step=100))
        self.now_row = Adw.SwitchRow(title="On right now", subtitle="Shortcut: SUPER + SHIFT + H")
        self.now_row.connect("notify::active", self._on_now)
        light.add(self.now_row)
        page.add(light)

        winddown = Adw.PreferencesGroup(
            title="Sleep wind-down",
            description="At bedtime the laptop helps you stop. It waits while you're in a game, a fullscreen "
                        "video or a call, and everything goes back to normal when the night light ends.")
        winddown.add(rows.switch_row(store, "night.winddown", "Wind down at bedtime"))
        winddown.add(rows.time_row(store, "night.winddown_time", "Bedtime"))
        winddown.add(rows.switch_row(store, "night.smart_bedtime", "Smart bedtime",
                                     "Each week, fits the bedtime to when you really stop, then moves it "
                                     "15 minutes earlier while you keep to it"))
        winddown.add(rows.time_row(store, "night.bedtime_goal", "Bedtime goal",
                                   "Smart bedtime never goes earlier than this"))
        self.suggestion = None
        self.suggest_row = Adw.ActionRow(title="Suggested bedtime", subtitle="…", subtitle_lines=4)
        self.use_button = Gtk.Button(label="Use it", valign=Gtk.Align.CENTER, visible=False)
        self.use_button.connect("clicked", lambda _b: self._use_suggestion())
        self.suggest_row.add_suffix(self.use_button)
        winddown.add(self.suggest_row)
        winddown.add(rows.switch_row(store, "night.winddown_dim", "Warmer, dimmer screen",
                                     "Eases in over 30 minutes, so it never feels sudden"))
        winddown.add(rows.switch_row(store, "night.winddown_quiet", "Quiet notifications",
                                     "Do not disturb until morning (urgent ones still come through)"))
        winddown.add(rows.switch_row(store, "night.winddown_reminders", "Bedtime reminders",
                                     "At bedtime, and once more 30 minutes later if you're still on"))
        winddown.add(rows.entry_row(store, "night.winddown_message", "Reminder message"))
        winddown.add(rows.button_row("Preview", "Show the reminder now", "Show",
                                     lambda: run_async([lennox_bin("lennox-winddown")]), "weather-clear-night-symbolic"))
        page.add(winddown)

        self.stats = Adw.PreferencesGroup(
            title="Sleep stats",
            description="When you actually stopped using the laptop each night (idle and locked time don't "
                        "count). A summary comes every Monday. Stays on this laptop.")
        self.stats.add(rows.switch_row(store, "night.sleep_stats", "Keep sleep stats"))
        self.stat_rows = []
        page.add(self.stats)
        self.widget = page

    def refresh(self):
        def got(_ok, out, _err):
            self.updating = True
            self.now_row.set_active(out.strip() == "on")
            self.updating = False

        run_async([lennox_bin("lennox-nightlight"), "status"], got)

        def got_stats(ok, out, _err):
            for row in self.stat_rows:
                self.stats.remove(row)
            self.stat_rows = []
            try:
                nights = json.loads(out) if ok else []
            except ValueError:
                nights = []
            if not nights:
                nights_rows = [rows.info_row("Last 7 nights", "Nothing yet: check back tomorrow")]
            else:
                nights_rows = []
                for item in nights:
                    try:
                        day = datetime.date.fromisoformat(item["night"]).strftime("%A %-d %b")
                    except (KeyError, ValueError):
                        continue
                    nights_rows.append(rows.info_row(day, f"off at {item.get('last', '?')}"))
            for row in nights_rows:
                self.stats.add(row)
                self.stat_rows.append(row)

        run_async([lennox_bin("lennox-winddown"), "stats", "--json"], got_stats)
        run_async([lennox_bin("lennox-bedtime"), "suggest", "--json"], self._got_suggestion)

    def _got_suggestion(self, ok, out, _err):
        try:
            result = json.loads(out) if ok else None
        except ValueError:
            result = None
        if not isinstance(result, dict):
            self.suggest_row.set_subtitle("Not available yet")
            self.use_button.set_visible(False)
            return
        changes = result.get("suggestion") != result.get("current") and result.get("kind") != "learning"
        self.suggest_row.set_title(f"Suggested bedtime: {result['suggestion']}" if changes else "Suggested bedtime")
        self.suggest_row.set_subtitle(GLib.markup_escape_text(result.get("text", "")))
        self.use_button.set_visible(changes)
        self.suggestion = result["suggestion"] if changes else None

    def _use_suggestion(self):
        if self.suggestion:
            self.ctx.store.set("night.winddown_time", self.suggestion)
            self.ctx.toast(f"Bedtime is now {self.suggestion}")
            self.refresh()

    def _on_now(self, row, _param):
        if not self.updating:
            run_async([lennox_bin("lennox-nightlight"), "on" if row.get_active() else "off"])
