"""Night: night light, sleep wind-down and sleep stats."""

import datetime
import json

from gi.repository import Adw

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

    def _on_now(self, row, _param):
        if not self.updating:
            run_async([lennox_bin("lennox-nightlight"), "on" if row.get_active() else "off"])
