"""Focus mode: start a session, choose what's blocked, see how much you focused."""

import json
import time

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async

QUICK = [25, 50, 90]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        now = Adw.PreferencesGroup(
            title="Focus",
            description="A timed session where distracting apps close, distracting sites don't load and "
                        "notifications wait. Then a short break. SUPER + F12, the quick panel or the island "
                        "start and stop it.")
        self.now_row = Adw.ActionRow(title="Not focusing")
        self.now_row.add_prefix(Gtk.Image.new_from_icon_name("find-location-symbolic"))
        self.buttons = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.now_row.add_suffix(self.buttons)
        now.add(self.now_row)
        page.add(now)

        setup = Adw.PreferencesGroup(title="How it works")
        setup.add(rows.spin_row(store, "focus.minutes", "Session length", "Minutes (SUPER + F12 starts this)",
                                lower=5, upper=240, step=5))
        setup.add(rows.spin_row(store, "focus.break_minutes", "Break after it", "Minutes (0 = no break)",
                                lower=0, upper=60, step=1))
        setup.add(rows.entry_row(store, "focus.block_apps", "Apps that close (names, commas between)"))
        setup.add(rows.entry_row(store, "focus.block_sites", "Sites that don't load (commas between)"))
        setup.add(rows.switch_row(store, "focus.quiet", "Hold notifications",
                                  "They wait in the quick panel until the session ends"))
        setup.add(rows.switch_row(store, "focus.sound", "Sound at the end"))
        page.add(setup)

        stats = Adw.PreferencesGroup(title="Your focus")
        self.today_row = rows.info_row("Today", "…")
        self.week_row = rows.info_row("Last 7 days", "…")
        self.streak_row = rows.info_row("Streak", "…")
        for row in (self.today_row, self.week_row, self.streak_row):
            stats.add(row)
        self.chart = Gtk.Box(spacing=10, homogeneous=True, margin_top=12, margin_bottom=6, height_request=110)
        stats.add(self.chart)
        page.add(stats)
        self.widget = page
        self.timer = None

    # ------------------------------------------------------------ now

    def refresh(self):
        run_async([lennox_bin("lennox-focus"), "status"], self._got_status)
        run_async([lennox_bin("lennox-focus"), "stats"], self._got_stats)
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(1, self._tick)

    def _tick(self):
        if not self.widget.get_mapped():
            self.timer = None
            return GLib.SOURCE_REMOVE
        run_async([lennox_bin("lennox-focus"), "status"], self._got_status)
        return GLib.SOURCE_CONTINUE

    def _set_buttons(self, specs):
        child = self.buttons.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.buttons.remove(child)
            child = nxt
        for label, argv, classes in specs:
            button = Gtk.Button(label=label, css_classes=classes)
            button.connect("clicked", lambda _b, a=argv: self._run(a))
            self.buttons.append(button)

    def _run(self, argv):
        run_async([lennox_bin("lennox-focus"), *argv], lambda *_a: self.refresh())

    def _got_status(self, ok, out, _err):
        try:
            info = json.loads(out) if ok else {}
        except ValueError:
            info = {}
        key = (info.get("active"), info.get("phase"))
        if info.get("active"):
            left = int(info.get("left", 0))
            clock = f"{left // 60}:{left % 60:02d}"
            if info["phase"] == "focus":
                self.now_row.set_title(f"Focusing · {clock} left")
                self.now_row.set_subtitle(f"Ends at {time.strftime('%H:%M', time.localtime(info['end']))}")
            else:
                self.now_row.set_title(f"Break · {clock} left")
                self.now_row.set_subtitle("Stand up, stretch, drink some water")
        else:
            self.now_row.set_title("Not focusing")
            self.now_row.set_subtitle("Start a session:")
        if key == getattr(self, "_shown", None):
            return
        self._shown = key
        if not info.get("active"):
            self._set_buttons([(f"{m} min", ["start", str(m)], ["suggested-action"] if m == 50 else [])
                               for m in QUICK])
        elif info["phase"] == "focus":
            self._set_buttons([("+5 min", ["more", "5"], []), ("Stop", ["stop"], ["destructive-action"])])
        else:
            self._set_buttons([("Skip break", ["stop"], [])])

    # ------------------------------------------------------------ stats

    def _got_stats(self, ok, out, _err):
        try:
            st = json.loads(out) if ok else None
        except ValueError:
            st = None
        if not isinstance(st, dict):
            return
        self.today_row.value_label.set_label(_hours(st["today"]) + f" · {st['sessions_today']} session"
                                             + ("s" if st["sessions_today"] != 1 else ""))
        self.week_row.value_label.set_label(_hours(st["week"]))
        self.streak_row.value_label.set_label(f"{st['streak']} day" + ("s" if st["streak"] != 1 else "")
                                              if st["streak"] else "Focus today to start one")
        child = self.chart.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.chart.remove(child)
            child = nxt
        top = max([d["minutes"] for d in st["days"]] + [30])
        for d in st["days"]:
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.END)
            bar = Gtk.LevelBar(orientation=Gtk.Orientation.VERTICAL, inverted=True, min_value=0, max_value=top,
                               value=d["minutes"], height_request=70, halign=Gtk.Align.CENTER,
                               tooltip_text=_hours(d["minutes"]))
            column.append(bar)
            day = time.strftime("%a", time.strptime(d["day"], "%Y-%m-%d"))
            column.append(Gtk.Label(label=day, css_classes=["dim-label", "caption"]))
            self.chart.append(column)


def _hours(minutes):
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"
