"""Display: brightness, scaling and arranging several screens."""

import json
import os

from gi.repository import Adw

from .. import rows
from ..util import HOME, Debouncer, launch, read_file, run_async

SCALES = [(1.0, "100%"), (1.25, "125%"), (1.5, "150%"), (1.75, "175%"), (2.0, "200%")]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        screen = Adw.PreferencesGroup(title="Screen")
        self.brightness_debounce = Debouncer(80, lambda v: run_async(["brightnessctl", "-q", "set", f"{int(v)}%"]))
        self.brightness = rows.scale_row("Brightness", "Also on your keyboard's brightness keys", 5, 100, 50,
                                         lambda v: None if self.updating else self.brightness_debounce.trigger(v))
        screen.add(self.brightness)
        self.scale_row = rows.combo_row(store, "display.scale", "Size of everything (scale)", SCALES)
        screen.add(self.scale_row)
        page.add(screen)

        monitors = Adw.PreferencesGroup(title="Connected screens",
                                        description="Plug in a screen, then arrange it here. On this laptop, HDMI may be "
                                                    "wired to the NVIDIA GPU: Lennox switches it on for you at the next login "
                                                    "(see Graphics).")
        self.monitor_rows = []
        self.monitor_group = monitors
        monitors.add(rows.link_row("Arrange displays", "Position, resolution and refresh rate of each screen",
                                   lambda: launch(["nwg-displays"]), "video-display-symbolic"))
        page.add(monitors)

        night = Adw.PreferencesGroup()
        night.add(rows.link_row("Night light", "Warmer colors in the evening",
                                lambda: ctx.navigate("night"), "weather-clear-night-symbolic"))
        page.add(night)

        self.updating = False
        self.widget = page

    def refresh(self):
        def got_brightness(ok, out, _err):
            if ok and out.strip():
                try:
                    value = int(out.strip().splitlines()[0].split(",")[3].rstrip("%"))
                except (IndexError, ValueError):
                    return
                self.updating = True
                self.brightness.scale.set_value(value)
                self.updating = False
            else:
                self.brightness.set_visible(False)

        run_async(["brightnessctl", "-m"], got_brightness)

        custom = read_file(os.path.join(HOME, ".config", "hypr", "monitors.lua"))
        if "hl.monitor" in custom:
            self.scale_row.set_subtitle("Arranged screens keep the scale set in \"Arrange displays\"")

        def got_monitors(ok, out, _err):
            for row in self.monitor_rows:
                self.monitor_group.remove(row)
            self.monitor_rows = []
            if not ok:
                return
            try:
                monitors = json.loads(out)
            except ValueError:
                return
            for m in monitors:
                title = f"{m.get('name')}  ·  {m.get('make', '')} {m.get('model', '')}".strip()
                value = f"{m.get('width')}×{m.get('height')} @ {round(m.get('refreshRate', 0))} Hz · scale {m.get('scale')}"
                row = rows.info_row(title, value)
                self.monitor_group.add(row)
                self.monitor_rows.append(row)

        run_async(["hyprctl", "-j", "monitors"], got_monitors)
