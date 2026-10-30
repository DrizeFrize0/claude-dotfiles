"""Widgets: the dashboard (SUPER + D) and the widgets on your desktop."""

import json
import threading

from gi.repository import Adw, GLib

from ... import aispend
from ...widgets import data as weather_data
from .. import rows
from ..util import launch, lennox_bin, run_async

POSITIONS = [
    ("top-left", "Top left"),
    ("top-center", "Top middle"),
    ("top-right", "Top right"),
    ("center", "Middle of the screen"),
    ("bottom-left", "Bottom left"),
    ("bottom-right", "Bottom right"),
]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        dash = Adw.PreferencesGroup(
            title="Dashboard",
            description="Slides in from the left: quick actions, volume and brightness, music, weather, "
                        "calendar, system and notes. Escape or a click next to it closes it.")
        dash.add(rows.button_row("Open the dashboard", "Shortcut: SUPER + D", "Open",
                                 lambda: launch([lennox_bin("lennox-widgets"), "dashboard", "open"]),
                                 "view-app-grid-symbolic"))
        page.add(dash)

        desktop = Adw.PreferencesGroup(
            title="Desktop widgets",
            description="On your wallpaper, behind your windows. Shortcut: SUPER + CTRL + W shows or hides them.")
        desktop.add(rows.switch_row(store, "widgets.desktop", "Show desktop widgets"))
        desktop.add(rows.combo_row(store, "widgets.position", "Position", POSITIONS))
        desktop.add(rows.switch_row(store, "widgets.show_clock", "Clock and date"))
        desktop.add(rows.switch_row(store, "widgets.show_greeting", "Greeting", "Good morning, good evening…"))
        desktop.add(rows.switch_row(store, "widgets.show_weather", "Weather", "Needs your city (below)"))
        desktop.add(rows.switch_row(store, "widgets.show_media", "Now playing", "Only shows while music or a video plays"))
        desktop.add(rows.switch_row(store, "widgets.show_system", "System", "Processor, memory, disk, battery"))
        desktop.add(rows.entry_row(store, "widgets.name", "Your name in the greeting (empty = account name)"))
        page.add(desktop)

        weather = Adw.PreferencesGroup(title="Weather", description="From Open-Meteo: free, no account needed.")
        weather.add(rows.entry_row(store, "widgets.weather_city", "City",
                                   on_applied=lambda ok, _text: ok and self._test_weather()))
        weather.add(rows.combo_row(store, "widgets.temperature_unit", "Temperature",
                                   [("celsius", "Celsius (°C)"), ("fahrenheit", "Fahrenheit (°F)")]))
        self.weather_row = rows.button_row("Check the weather", "", "Check", self._test_weather,
                                           "weather-few-clouds-symbolic")
        self.weather_row.set_use_markup(False)
        weather.add(self.weather_row)
        page.add(weather)

        ai = Adw.PreferencesGroup(
            title="AI spend",
            description="What you spend on AI coding (Claude Code, Codex, Cursor…), read from CodeBurn. "
                        "Shows today's cost in the bar; click it for the CodeBurn dashboard.")
        ai.add(rows.switch_row(store, "ai.spend_widget", "Show in the bar"))
        ai.add(rows.spin_row(store, "ai.monthly_budget", "Monthly budget",
                             "Warns at 80% and 100%. 0 turns warnings off", lower=0, upper=100000, step=10))
        self.ai_row = rows.info_row("This month", "checking…")
        ai.add(self.ai_row)
        ai.add(rows.button_row("Read CodeBurn again", "It refreshes by itself every 5 minutes", "Refresh",
                               self._refresh_ai, "view-refresh-symbolic"))
        page.add(ai)

        extra = Adw.PreferencesGroup(title="Make it yours")
        extra.add(rows.info_row("Your picture", "~/.face (a square image)"))
        extra.add(rows.info_row("Custom style", "~/.config/lennox/widgets.css"))
        page.add(extra)
        self.widget = page

    def refresh(self):
        def got(ok, out, err):
            try:
                spend = json.loads(out) if ok else None
            except ValueError:
                spend = None
            if not spend:
                self.ai_row.value_label.set_label("Needs CodeBurn's command: yay -S codeburn")
                return
            cur = spend["currency"]
            text = f"{aispend.money(spend['month'], cur)} (today {aispend.money(spend['today'], cur)})"
            if spend["budget"] > 0:
                text += f" · {spend['month'] / spend['budget'] * 100:.0f}% of budget"
            self.ai_row.value_label.set_label(text)

        run_async([lennox_bin("lennox-aispend")], got)

    def _refresh_ai(self):
        self.ai_row.value_label.set_label("reading CodeBurn…")
        run_async([lennox_bin("lennox-aispend"), "refresh-bar"], lambda *_: self.refresh())

    def _test_weather(self):
        city = self.ctx.store.get("widgets.weather_city")
        unit = self.ctx.store.get("widgets.temperature_unit")
        self.weather_row.set_subtitle("Checking…")

        def work():
            try:
                w = weather_data.weather(city, unit, force=True)
                text = f"{w['temp']}{w['unit']}, {w['text']} in {w['place']}"
            except weather_data.WeatherError as e:
                text = str(e)
            GLib.idle_add(lambda: (self.weather_row.set_subtitle(text), False)[1])
        threading.Thread(target=work, daemon=True).start()
