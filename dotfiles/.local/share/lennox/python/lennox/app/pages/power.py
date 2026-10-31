"""Power & Battery: power profile, battery saver, sleep and lock timers."""

import glob
import os

from gi.repository import Adw, Gtk

from .. import rows
from ..util import lennox_bin, read_file, run_async

PROFILE_LABELS = {"performance": "Performance", "balanced": "Balanced", "power-saver": "Battery saver"}


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        self.profiles = []
        store = ctx.store
        page = Adw.PreferencesPage()

        battery = Adw.PreferencesGroup(title="Battery")
        self.battery_row = rows.info_row("Battery", "…")
        battery.add(self.battery_row)
        self.profile_row = Adw.ComboRow(title="Power mode", subtitle="Performance for games, battery saver on the go")
        self.profile_row.connect("notify::selected", self._on_profile)
        battery.add(self.profile_row)
        battery.add(rows.switch_row(store, "power.saver_on_battery", "Battery saver when unplugged",
                                    "Power-saver mode and lighter effects; back to normal when you plug in"))
        battery.add(rows.spin_row(store, "power.low_battery_warning", "Warn me at", "Percent", lower=5, upper=50))
        battery.add(rows.spin_row(store, "power.critical_battery", "Urgent warning at", "Percent", lower=2, upper=20))
        page.add(battery)
        self.battery_group = battery

        idle = Adw.PreferencesGroup(title="When you're away", description="Minutes. 0 means never.")
        idle.add(rows.spin_row(store, "idle.dim_minutes", "Dim the screen after", lower=0, upper=240))
        idle.add(rows.spin_row(store, "idle.lock_minutes", "Lock after", lower=0, upper=240))
        idle.add(rows.spin_row(store, "idle.screen_off_minutes", "Turn the screen off after", lower=0, upper=240))
        idle.add(rows.spin_row(store, "idle.suspend_minutes", "Sleep after", lower=0, upper=480, step=5))
        idle.add(rows.switch_row(store, "idle.suspend_on_ac", "Also sleep while charging",
                                 "Off: downloads and servers keep running when plugged in"))
        idle.add(rows.switch_row(store, "idle.lock_before_sleep", "Lock when the lid closes or the laptop sleeps"))
        self.awake_row = Adw.SwitchRow(title="Stay awake for now",
                                       subtitle="Pause auto lock and sleep until you turn this off or log out")
        self.awake_row.connect("notify::active", self._on_awake)
        idle.add(self.awake_row)
        page.add(idle)

        panic = Adw.PreferencesGroup(
            title="Panic key",
            description="SUPER + CTRL + BACKSPACE when somebody walks in. After you unlock, your windows "
                        "come back where they were and the sound returns.")
        panic.add(rows.switch_row(ctx.store, "panic.hide", "Hide every window"))
        panic.add(rows.switch_row(ctx.store, "panic.mute", "Pause the music and mute the sound"))
        panic.add(rows.switch_row(ctx.store, "panic.lock", "Lock the screen",
                                  "Off: press it again to bring everything back"))
        page.add(panic)
        self.widget = page

    def refresh(self):
        batteries = [b for b in glob.glob("/sys/class/power_supply/BAT*")]
        if batteries:
            b = batteries[0]
            capacity = read_file(os.path.join(b, "capacity")).strip()
            status = read_file(os.path.join(b, "status")).strip()
            self.battery_row.value_label.set_label(f"{capacity}% · {status}")
        else:
            self.battery_row.set_visible(False)

        def got_profiles(ok, out, _err):
            profiles = []
            current = None
            if ok:
                for line in out.splitlines():
                    stripped = line.strip()
                    if stripped.endswith(":") and not stripped.startswith(("Driver", "Degraded", "PlatformDriver", "CpuDriver")):
                        name = stripped.lstrip("* ").rstrip(":")
                        profiles.append(name)
                        if stripped.startswith("*"):
                            current = name
            self.updating = True
            self.profiles = profiles
            self.profile_row.set_model(Gtk.StringList.new([PROFILE_LABELS.get(p, p) for p in profiles]))
            self.profile_row.set_visible(bool(profiles))
            if current in profiles:
                self.profile_row.set_selected(profiles.index(current))
            self.updating = False

        run_async(["powerprofilesctl", "list"], got_profiles)

        def got_idle(_ok, out, _err):
            self.updating = True
            self.awake_row.set_active(out.strip() == "off")
            self.updating = False

        run_async([lennox_bin("lennox-idle"), "status"], got_idle)

    def _on_profile(self, row, _param):
        if self.updating:
            return
        index = row.get_selected()
        if 0 <= index < len(self.profiles):
            profile = self.profiles[index]
            run_async(["powerprofilesctl", "set", profile],
                      lambda ok, _o, err: self.ctx.toast(f"Power mode: {PROFILE_LABELS.get(profile, profile)}"
                                                         if ok else f"Could not switch: {err.strip()}"))

    def _on_awake(self, row, _param):
        if not self.updating:
            run_async([lennox_bin("lennox-idle"), "off" if row.get_active() else "on"])
