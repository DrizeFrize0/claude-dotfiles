"""Lennox Clock: world clock, alarms, timers, stopwatch and reminders.

The app only edits ~/.local/state/lennox/clock.json (through lennox.clock);
the widgets process fires everything, so alarms ring with the app closed.
"""

import datetime
import os
import sys
import time
import zoneinfo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import clock as C  # noqa: E402

APP_ID = "dev.lennox.Clock"
TIMER_PRESETS = [("1 min", 60), ("3 min", 180), ("5 min", 300), ("10 min", 600),
                 ("15 min", 900), ("25 min", 1500), ("45 min", 2700), ("1 hour", 3600)]
DAY_CHOICES = [("Once", ""), ("Every day", "daily"), ("Weekdays", "weekdays"), ("Weekends", "weekends")]

CSS = """
.clock-big { font-size: 56px; font-weight: 300; font-feature-settings: "tnum"; }
.clock-time { font-size: 28px; font-weight: 300; font-feature-settings: "tnum"; }
.clock-row-time { font-size: 20px; font-feature-settings: "tnum"; }
"""


def city(zone):
    return zone.split("/")[-1].replace("_", " ")


def find_zone(text):
    """'tokyo' -> 'Asia/Tokyo', 'new york' -> 'America/New_York', or None."""
    text = text.strip().lower().replace(" ", "_")
    if not text:
        return None
    zones = sorted(zoneinfo.available_timezones())
    for z in zones:
        if z.lower() == text or z.lower().split("/")[-1] == text:
            return z
    matches = [z for z in zones if text in z.lower() and "/" in z and not z.startswith(("Etc/", "SystemV/"))]
    return matches[0] if matches else None


def fmt_time(dt_value, h24):
    return dt_value.strftime("%H:%M") if h24 else dt_value.strftime("%-I:%M %p")


class ClockWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Clock")
        self.set_default_size(880, 660)
        self.h24 = self._h24()
        self.signature = None
        self.data = C.load()

        css = Gtk.CssProvider()
        try:
            css.load_from_string(CSS)
        except AttributeError:
            css.load_from_data(CSS, -1)
        Gtk.StyleContext.add_provider_for_display(self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.toasts = Adw.ToastOverlay()
        stack = Adw.ViewStack()
        self.stack = stack
        for name, title, icon, build in (
                ("world", "World", "globe-symbolic", self._world_page),
                ("alarms", "Alarms", "alarm-symbolic", self._alarms_page),
                ("timers", "Timers", "timer-symbolic", self._timers_page),
                ("stopwatch", "Stopwatch", "stopwatch-symbolic", self._stopwatch_page),
                ("reminders", "Reminders", "appointment-soon-symbolic", self._reminders_page)):
            stack.add_titled_with_icon(build(), name, title, icon)

        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", lambda _c, keyval, *_: keyval == 0xff1b and (self.close() or True))
        self.add_controller(key)

        self.refresh(force=True)
        GLib.timeout_add(250, self._tick)

    @staticmethod
    def _h24():
        try:
            from . import settings as S
            return bool(S.load()["bar"]["clock_24h"])
        except Exception:  # noqa: BLE001
            return True

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))

    def change(self, func):
        """Apply func(data, now) to clock.json and refresh."""
        with C.edit() as data:
            result = func(data, time.time())
        self.refresh(force=True)
        return result

    # ---------------------------------------------------------------- pages

    def _scrolled(self, *groups, top=None):
        page = Adw.PreferencesPage()
        for g in groups:
            page.add(g)
        if top is None:
            return page
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(top)
        page.set_vexpand(True)
        box.append(page)
        return box

    def _world_page(self):
        self.local_label = Gtk.Label(css_classes=["clock-big"], margin_top=18)
        self.local_date = Gtk.Label(css_classes=["dim-label"], margin_bottom=6)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top.append(self.local_label)
        top.append(self.local_date)
        self.world_group = Adw.PreferencesGroup(title="Other cities")
        add = Adw.EntryRow(title="Add a city (Tokyo, New York, Dubai…)", show_apply_button=True)
        add.connect("apply", self._add_city)
        self.world_group.add(add)
        self.world_rows = []
        return self._scrolled(self.world_group, top=top)

    def _alarms_page(self):
        new = Adw.PreferencesGroup(title="New alarm")
        self.alarm_time = Adw.EntryRow(title="Time (07:30 or 7:30am)")
        self.alarm_label = Adw.EntryRow(title="Label (optional)")
        self.alarm_days = Adw.ComboRow(title="Repeat", model=Gtk.StringList.new([d for d, _ in DAY_CHOICES]))
        add = Gtk.Button(label="Add alarm", halign=Gtk.Align.END, margin_top=8, css_classes=["suggested-action"])
        add.connect("clicked", lambda _b: self._add_alarm())
        for row in (self.alarm_time, self.alarm_label, self.alarm_days):
            new.add(row)
        new.add(add)
        self.alarm_group = Adw.PreferencesGroup(title="Alarms",
                                                description="They ring even with this window closed.")
        self.alarm_rows = []
        return self._scrolled(new, self.alarm_group)

    def _timers_page(self):
        presets = Adw.PreferencesGroup(title="Start a timer")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, column_spacing=6,
                           row_spacing=6, homogeneous=True)
        for label, seconds in TIMER_PRESETS:
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _b, s=seconds, lab=label: self._start_timer(s, ""))
            flow.append(button)
        presets.add(flow)
        self.timer_custom = Adw.EntryRow(title="Custom: 20m, 1h30m, 90s… then a label", show_apply_button=True)
        self.timer_custom.connect("apply", lambda r: self._custom_timer(r))
        presets.add(self.timer_custom)
        self.timer_group = Adw.PreferencesGroup(title="Running")
        self.timer_rows = []
        return self._scrolled(presets, self.timer_group)

    def _stopwatch_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24)
        self.sw_label = Gtk.Label(label="0:00.0", css_classes=["clock-big"])
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.sw_start = Gtk.Button(label="Start", css_classes=["suggested-action", "pill"])
        self.sw_start.connect("clicked", lambda _b: self._stopwatch_toggle())
        lap = Gtk.Button(label="Lap", css_classes=["pill"])
        lap.connect("clicked", lambda _b: self.change(lambda d, n: C.stopwatch(d, "lap", n)))
        reset = Gtk.Button(label="Reset", css_classes=["pill"])
        reset.connect("clicked", lambda _b: self.change(lambda d, n: C.stopwatch(d, "reset", n)))
        for b in (self.sw_start, lap, reset):
            buttons.append(b)
        box.append(self.sw_label)
        box.append(buttons)
        self.lap_group = Adw.PreferencesGroup(title="Laps")
        self.lap_rows = []
        return self._scrolled(self.lap_group, top=box)

    def _reminders_page(self):
        new = Adw.PreferencesGroup(title="New reminder",
                                   description="A notification that comes through even in Do not disturb.")
        self.rem_when = Adw.EntryRow(title="When: 18:00, 7pm, 20m, 1h")
        self.rem_text = Adw.EntryRow(title="What (check the server, take a break…)", show_apply_button=True)
        self.rem_text.connect("apply", lambda _r: self._add_reminder())
        add = Gtk.Button(label="Add reminder", halign=Gtk.Align.END, margin_top=8, css_classes=["suggested-action"])
        add.connect("clicked", lambda _b: self._add_reminder())
        new.add(self.rem_when)
        new.add(self.rem_text)
        new.add(add)
        self.rem_group = Adw.PreferencesGroup(title="Coming up")
        self.rem_rows = []
        return self._scrolled(new, self.rem_group)

    # ---------------------------------------------------------------- actions

    def _add_city(self, row):
        zone = find_zone(row.get_text())
        if not zone:
            self.toast(f"No city called '{row.get_text()}'")
            return
        row.set_text("")

        def add(data, _now):
            if zone not in data["world"]:
                data["world"].append(zone)
        self.change(add)

    def _add_alarm(self):
        hm = C.parse_time(self.alarm_time.get_text())
        if not hm:
            self.alarm_time.add_css_class("error")
            self.toast("Type a time like 07:30 or 7:30am")
            return
        self.alarm_time.remove_css_class("error")
        days = C.parse_days(DAY_CHOICES[self.alarm_days.get_selected()][1])
        label = self.alarm_label.get_text().strip()
        alarm = self.change(lambda d, n: C.add_alarm(d, hm[0], hm[1], label, days, n))
        self.alarm_time.set_text("")
        self.alarm_label.set_text("")
        if alarm.get("next"):
            self.toast(f"Alarm set for {datetime.datetime.fromtimestamp(alarm['next']):%A %H:%M}")

    def _start_timer(self, seconds, label):
        self.change(lambda d, n: C.add_timer(d, seconds, label, n))

    def _custom_timer(self, row):
        text = row.get_text().strip()
        first, _, label = text.partition(" ")
        seconds = C.parse_duration(first)
        if not seconds:
            self.toast("Type a length like 20m, 1h30m or 90s")
            return
        row.set_text("")
        self._start_timer(seconds, label)

    def _stopwatch_toggle(self):
        running = self.data["stopwatch"]["start"] is not None
        self.change(lambda d, n: C.stopwatch(d, "stop" if running else "start", n))

    def _add_reminder(self):
        at = C.when(self.rem_when.get_text(), time.time())
        if not at:
            self.rem_when.add_css_class("error")
            self.toast("Type when: 18:00, 7pm, 20m or 1h")
            return
        self.rem_when.remove_css_class("error")
        text = self.rem_text.get_text().strip()
        self.change(lambda d, n: C.add_reminder(d, at, text))
        self.rem_when.set_text("")
        self.rem_text.set_text("")
        self.toast(f"I'll remind you at {datetime.datetime.fromtimestamp(at):%H:%M}")

    # ---------------------------------------------------------------- refresh

    def _tick(self):
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def _replace(self, group, old_rows, new_rows):
        for row in old_rows:
            group.remove(row)
        old_rows.clear()
        for row in new_rows:
            group.add(row)
            old_rows.append(row)

    def _button(self, icon, tooltip, callback, css=None):
        b = Gtk.Button(icon_name=icon, tooltip_text=tooltip, valign=Gtk.Align.CENTER, css_classes=["flat"] + (css or []))
        b.connect("clicked", lambda _b: callback())
        return b

    def refresh(self, force=False):
        now = time.time()
        try:
            stamp = os.stat(C.CLOCK_FILE).st_mtime
        except OSError:
            stamp = 0
        if force or stamp != self.signature:
            self.signature = stamp
            self.data = C.load()
            self._rebuild(now)
        self._update(now)

    def _rebuild(self, now):
        d = self.data
        rows = []
        for zone in d["world"]:
            row = Adw.ActionRow(title=city(zone), use_markup=False)
            row.time_label = Gtk.Label(css_classes=["clock-row-time"])
            row.zone = zone
            row.add_suffix(row.time_label)
            row.add_suffix(self._button("user-trash-symbolic", "Remove",
                                        lambda z=zone: self.change(lambda dd, n: dd["world"].remove(z))))
            rows.append(row)
        self._replace(self.world_group, self.world_rows, rows)

        rows = []
        for a in sorted(d["alarms"], key=lambda x: x["time"]):
            row = Adw.ActionRow(title=a["time"] if self.h24 else fmt_time(
                datetime.datetime.strptime(a["time"], "%H:%M"), False), use_markup=False,
                subtitle=f"{a['label']} · {C.days_text(a['days'])}")
            row.add_css_class("clock-row-time")
            switch = Gtk.Switch(active=bool(a.get("enabled")), valign=Gtk.Align.CENTER)
            switch.connect("notify::active", lambda s, _p, i=a["id"]: self.change(
                lambda dd, n: C.set_alarm_enabled(dd, i, s.get_active(), n)))
            row.add_suffix(switch)
            row.add_suffix(self._button("user-trash-symbolic", "Delete",
                                        lambda i=a["id"]: self.change(lambda dd, n: C.cancel(dd, i))))
            rows.append(row)
        if not rows:
            rows.append(Adw.ActionRow(title="No alarms yet"))
        self._replace(self.alarm_group, self.alarm_rows, rows)

        rows = []
        for t in d["timers"]:
            row = Adw.ActionRow(title=t["label"], use_markup=False)
            row.timer = t
            row.left_label = Gtk.Label(css_classes=["clock-row-time"])
            row.add_suffix(row.left_label)
            paused = t.get("paused_left") is not None
            row.add_suffix(self._button("media-playback-start-symbolic" if paused else "media-playback-pause-symbolic",
                                        "Resume" if paused else "Pause",
                                        lambda i=t["id"]: self.change(lambda dd, n: C.pause_timer(dd, i, n))))
            row.add_suffix(self._button("user-trash-symbolic", "Cancel",
                                        lambda i=t["id"]: self.change(lambda dd, n: C.cancel(dd, i))))
            rows.append(row)
        for r in d["ringing"]:
            snooze, stop = (Gtk.Button(label="Snooze 10 min", valign=Gtk.Align.CENTER),
                            Gtk.Button(label="Stop", valign=Gtk.Align.CENTER, css_classes=["destructive-action"]))
            snooze.connect("clicked", lambda _b: self.change(lambda dd, n: C.snooze(dd, n)))
            stop.connect("clicked", lambda _b: self.change(lambda dd, n: C.stop_ringing(dd)))
            row = Adw.ActionRow(title=f"{r['label']}: ringing", use_markup=False)
            row.add_suffix(snooze)
            row.add_suffix(stop)
            rows.insert(0, row)
        if not rows:
            rows.append(Adw.ActionRow(title="No timers running"))
        self._replace(self.timer_group, self.timer_rows, rows)

        sw = d["stopwatch"]
        self.sw_start.set_label("Stop" if sw["start"] is not None else ("Resume" if sw["elapsed"] else "Start"))
        rows = []
        laps = sw["laps"]
        for i, lap in reversed(list(enumerate(laps))):
            split = lap - (laps[i - 1] if i else 0)
            row = Adw.ActionRow(title=f"Lap {i + 1}", subtitle=f"+{C.countdown(split)}")
            row.add_suffix(Gtk.Label(label=C.countdown(lap), css_classes=["clock-row-time"]))
            rows.append(row)
        self._replace(self.lap_group, self.lap_rows, rows)

        rows = []
        for r in sorted(d["reminders"], key=lambda x: x["at"]):
            when = datetime.datetime.fromtimestamp(r["at"])
            day = "Today" if when.date() == datetime.date.today() else when.strftime("%a %-d %b")
            row = Adw.ActionRow(title=r["text"], subtitle=f"{day} {fmt_time(when, self.h24)}", use_markup=False)
            row.add_suffix(self._button("user-trash-symbolic", "Delete",
                                        lambda i=r["id"]: self.change(lambda dd, n: C.cancel(dd, i))))
            rows.append(row)
        if not rows:
            rows.append(Adw.ActionRow(title="Nothing coming up"))
        self._replace(self.rem_group, self.rem_rows, rows)

    def _update(self, now):
        local = datetime.datetime.now().astimezone()
        self.local_label.set_label(local.strftime("%H:%M:%S") if self.h24 else local.strftime("%-I:%M:%S %p"))
        self.local_date.set_label(local.strftime("%A %-d %B · ") + (local.tzname() or ""))
        for row in self.world_rows:
            there = datetime.datetime.now(zoneinfo.ZoneInfo(row.zone))
            diff = (there.utcoffset() - local.utcoffset()).total_seconds() / 3600
            sign = "+" if diff >= 0 else "−"
            row.set_subtitle(f"{there:%a} · {sign}{abs(diff):g} h" if diff else f"{there:%a} · same time")
            row.time_label.set_label(fmt_time(there, self.h24))
        for row in self.timer_rows:
            t = getattr(row, "timer", None)
            if t:
                left = t["paused_left"] if t.get("paused_left") is not None else t["end"] - now
                row.left_label.set_label(C.countdown(left) + (" ⏸" if t.get("paused_left") is not None else ""))
        sw = self.data["stopwatch"]
        elapsed = C.stopwatch_elapsed(sw, now)
        self.sw_label.set_label(f"{C.countdown(elapsed)}.{int(elapsed * 10) % 10}")


class ClockApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if self.window is None:
            self.window = ClockWindow(self)
        if args and args[0] in ("world", "alarms", "timers", "stopwatch", "reminders"):
            self.window.stack.set_visible_child_name(args[0])
        self.window.present()
        return 0


def main(argv=None):
    return ClockApp().run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
