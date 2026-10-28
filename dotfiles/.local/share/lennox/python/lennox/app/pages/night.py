"""Night: night light and the wind-down reminder."""

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

        winddown = Adw.PreferencesGroup(title="Wind-down reminder",
                                        description="One quiet notification at night. No nagging, no repeats.")
        winddown.add(rows.switch_row(store, "night.winddown", "Remind me"))
        winddown.add(rows.time_row(store, "night.winddown_time", "At"))
        winddown.add(rows.entry_row(store, "night.winddown_message", "Message"))
        winddown.add(rows.button_row("Preview", "Show the reminder now", "Show",
                                     lambda: run_async([lennox_bin("lennox-winddown")]), "weather-clear-night-symbolic"))
        page.add(winddown)
        self.widget = page

    def refresh(self):
        def got(_ok, out, _err):
            self.updating = True
            self.now_row.set_active(out.strip() == "on")
            self.updating = False

        run_async([lennox_bin("lennox-nightlight"), "status"], got)

    def _on_now(self, row, _param):
        if not self.updating:
            run_async([lennox_bin("lennox-nightlight"), "on" if row.get_active() else "off"])
