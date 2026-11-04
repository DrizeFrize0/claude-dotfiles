"""Daily care: water reminder, heat alerts, prayer times."""

import datetime

from gi.repository import Adw

from .. import rows
from ... import care as C
from ... import mood as M
from ... import settings as S


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        hello = Adw.PreferencesGroup(title="Greeting", description="A short hello a few seconds after you log in: "
                                     "the weather, your next prayer and alarm, and your focus streak.")
        hello.add(rows.switch_row(store, "greeting.animation", "Welcome animation at login", "Stars and your name fade in for a few seconds"))
        hello.add(rows.switch_row(store, "greeting.on", "Say hello at login"))
        hello.add(rows.entry_row(store, "greeting.name", "What should I call you? (empty: your user name)"))
        page.add(hello)

        diary = Adw.PreferencesGroup(title="Mood and sleep", description="One tap each evening for how the day was. Everything stays on this laptop.")
        diary.add(rows.switch_row(store, "mood.on", "Ask me every evening"))
        diary.add(rows.time_row(store, "mood.time", "Ask at"))
        self.week_row = rows.info_row("This week", "…")
        diary.add(self.week_row)
        self.tip_rows = []
        self.diary = diary
        page.add(diary)

        water = Adw.PreferencesGroup(
            title="Water", description="A gentle nudge after every stretch at the laptop. It waits while "
                                        "you're gaming, focusing or the screen is locked.")
        water.add(rows.switch_row(store, "care.water", "Remind me to drink water"))
        water.add(rows.spin_row(store, "care.water_minutes", "Every", "Minutes at the laptop", lower=15, upper=240, step=5))
        page.add(water)

        heat = Adw.PreferencesGroup(
            title="Heat", description="A warning when the laptop stays too hot for a minute, with one tap to "
                                      "switch to Quiet mode. The graphics chip is only checked while it's awake "
                                      "(in a game), so this never wakes it.")
        heat.add(rows.switch_row(store, "care.heat", "Warn me when it gets too hot"))
        heat.add(rows.switch_row(store, "care.heat_auto", "Switch to Quiet mode by itself", "Not while you are gaming: then you get a button instead"))
        heat.add(rows.spin_row(store, "care.heat_cpu", "Processor limit", "Degrees C", lower=70, upper=105))
        heat.add(rows.spin_row(store, "care.heat_gpu", "Graphics limit", "Degrees C", lower=65, upper=100))
        self.temp_row = rows.info_row("Right now", "…")
        heat.add(self.temp_row)
        page.add(heat)

        prayer = Adw.PreferencesGroup(
            title="Prayer times", description="Worked out on this laptop (no internet), by default for Amman with "
                                              "the Jordan Ministry of Awqaf method: Fajr and Isha at 18°. "
                                              "Change the place below for anywhere else.")
        prayer.add(rows.switch_row(store, "care.prayer", "Remind me of prayer times"))
        prayer.add(rows.spin_row(store, "care.prayer_remind", "Remind me before", "Minutes (0 = not before)",
                                 lower=0, upper=60))
        prayer.add(rows.switch_row(store, "care.prayer_at_time", "Also when the time comes"))
        prayer.add(rows.spin_row(store, "care.prayer_lat", "Latitude", "Amman: 31.95", lower=-66, upper=66, step=0.01, digits=2))
        prayer.add(rows.spin_row(store, "care.prayer_lon", "Longitude", "Amman: 35.93", lower=-180, upper=180, step=0.01, digits=2))
        self.prayer_group = prayer
        self.prayer_rows = []
        page.add(prayer)
        self.widget = page
        self.refresh()

    def refresh(self):
        cpu = C.cpu_temp()
        self.temp_row.value_label.set_text(f"Processor {cpu:.0f}°C" if cpu is not None else "The laptop doesn't report it")
        week = M.week(M.load())
        self.week_row.value_label.set_label("  ".join(M.FACES[d["mood"] - 1] if d["mood"] else "·" for d in week))
        for row in self.tip_rows:
            self.diary.remove(row)
        self.tip_rows = []
        for tip in M.report_text():
            row = rows.info_row("Why am I tired?" if not self.tip_rows else "", "")
            row.set_subtitle(tip)
            row.value_label.set_visible(False)
            self.diary.add(row)
            self.tip_rows.append(row)
        for row in self.prayer_rows:
            self.prayer_group.remove(row)
        self.prayer_rows = []
        s = S.load()["care"]
        now = datetime.datetime.now()
        times = C.prayer_times(now.date(), s["prayer_lat"], s["prayer_lon"], C.tz_hours())
        for name, at in times.items():
            en, ar = C.NAMES[name]
            row = rows.info_row(f"{en}  {ar}", at.strftime("%H:%M"))
            self.prayer_group.add(row)
            self.prayer_rows.append(row)
