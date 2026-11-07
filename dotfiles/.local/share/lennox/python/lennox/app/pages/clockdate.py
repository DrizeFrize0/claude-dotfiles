"""Date & time: time zone, automatic time from the internet, 12 or 24 hour clock."""

from gi.repository import Adw, Gtk

from .. import rows
from ..util import run_async


def parse_status(text):
    """`timedatectl show` (KEY=value lines) -> dict."""
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.zones = []
        self.loading = False
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="Date & time", description="So the clock never needs the terminal.")
        self.now_row = rows.info_row("Now", "…")
        group.add(self.now_row)
        self.zone_row = Adw.ComboRow(title="Time zone", enable_search=True)
        self.zone_row.connect("notify::selected", self._on_zone)
        group.add(self.zone_row)
        self.ntp_row = Adw.SwitchRow(title="Set the time automatically", subtitle="From the internet")
        self.ntp_row.connect("notify::active", self._on_ntp)
        group.add(self.ntp_row)
        group.add(rows.switch_row(ctx.store, "bar.clock_24h", "24-hour clock", "Off: 3:45 PM. The bar and the island follow it"))
        page.add(group)
        self.widget = page

    def refresh(self):
        run_async(["timedatectl", "show"], self._got_status)
        if not self.zones:
            run_async(["timedatectl", "list-timezones"], self._got_zones)

    def _got_zones(self, ok, out, _err):
        if ok:
            self.zones = [z for z in out.split() if z]
            self.loading = True
            self.zone_row.set_model(Gtk.StringList.new(self.zones))
            self.loading = False
            self.refresh()

    def _got_status(self, ok, out, _err):
        if not ok:
            self.now_row.value_label.set_label("timedatectl isn't available")
            return
        st = parse_status(out)
        self.now_row.value_label.set_label(f"{st.get('TimeUSec', '')}")
        self.loading = True
        if st.get("Timezone") in self.zones:
            self.zone_row.set_selected(self.zones.index(st["Timezone"]))
        self.ntp_row.set_active(st.get("NTP") == "yes")
        self.loading = False

    def _on_zone(self, row, _p):
        if self.loading or not self.zones:
            return
        zone = self.zones[row.get_selected()]
        run_async(["timedatectl", "set-timezone", zone],
                  lambda ok, _o, err: self.ctx.toast(f"Time zone: {zone}" if ok else (err.strip() or "Couldn't change it")))

    def _on_ntp(self, row, _p):
        if self.loading:
            return
        run_async(["timedatectl", "set-ntp", "true" if row.get_active() else "false"],
                  lambda ok, _o, err: ok or self.ctx.toast(err.strip() or "Couldn't change it"))


__all__ = ["Page", "parse_status"]
