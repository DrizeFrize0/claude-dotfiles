"""Appearance: dark/light, colors, animations, windows."""

from gi.repository import Adw, Gtk

from .. import rows

# One-click looks: they set several values at once
PRESETS = {
    "ML4W Default": {"border_style": "gradient", "gaps_in": 10, "gaps_out": 16, "border_size": 2,
                     "rounding": 10, "blur": True, "shadow": True, "inactive_opacity": 0.9,
                     "animations": "default"},
    "Glass": {"border_style": "gradient", "gaps_in": 10, "gaps_out": 16, "border_size": 1,
              "rounding": 14, "blur": True, "shadow": True, "inactive_opacity": 0.85,
              "animations": "smooth"},
    "Minimal": {"border_style": "solid", "gaps_in": 4, "gaps_out": 8, "border_size": 1,
                "rounding": 6, "blur": False, "shadow": False, "inactive_opacity": 1.0,
                "animations": "fast"},
    "No gaps": {"border_style": "none", "gaps_in": 0, "gaps_out": 0, "border_size": 0,
                "rounding": 0, "blur": False, "shadow": False, "inactive_opacity": 1.0,
                "animations": "fast"},
}

SCHEMES = [
    ("scheme-tonal-spot", "Calm (ML4W default)"),
    ("scheme-content", "True to the wallpaper"),
    ("scheme-vibrant", "Vibrant"),
    ("scheme-expressive", "Expressive"),
    ("scheme-fidelity", "Fidelity"),
    ("scheme-rainbow", "Rainbow"),
    ("scheme-fruit-salad", "Fruit salad"),
    ("scheme-neutral", "Neutral"),
    ("scheme-monochrome", "Monochrome"),
]

ANIMATIONS = [
    ("default", "Default (ML4W)"),
    ("fast", "Fast"),
    ("smooth", "Smooth"),
    ("bouncy", "Bouncy"),
    ("off", "Off"),
]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        colors = Adw.PreferencesGroup(title="Colors", description="All colors are picked from your wallpaper.")
        colors.add(rows.combo_row(store, "appearance.color_mode", "Mode",
                                  [("dark", "Dark"), ("light", "Light")],
                                  "Shortcut: SUPER + SHIFT + M"))
        colors.add(rows.combo_row(store, "appearance.color_scheme", "Color style", SCHEMES))
        page.add(colors)

        presets = Adw.PreferencesGroup(title="Looks", description="Start from a look, then fine-tune below.")
        box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                          column_spacing=8, row_spacing=8, homogeneous=True)
        for name in PRESETS:
            button = Gtk.Button(label=name)
            button.add_css_class("pill")
            button.connect("clicked", self._apply_preset, name)
            box.append(button)
        presets.add(box)
        page.add(presets)

        windows = Adw.PreferencesGroup(title="Windows")
        windows.add(rows.combo_row(store, "appearance.animations", "Animations", ANIMATIONS))
        windows.add(rows.combo_row(store, "appearance.border_style", "Border",
                                   [("gradient", "Gradient (ML4W)"), ("solid", "Solid"), ("none", "None")]))
        windows.add(rows.spin_row(store, "appearance.border_size", "Border width", lower=0, upper=8))
        windows.add(rows.spin_row(store, "appearance.rounding", "Rounded corners", lower=0, upper=30))
        windows.add(rows.spin_row(store, "appearance.gaps_in", "Gap between windows", lower=0, upper=40))
        windows.add(rows.spin_row(store, "appearance.gaps_out", "Gap to the screen edge", lower=0, upper=60))
        windows.add(rows.combo_row(store, "appearance.layout", "Tiling layout",
                                   [("dwindle", "Dwindle (split in half)"), ("master", "Master (one big window)")]))
        page.add(windows)

        effects = Adw.PreferencesGroup(title="Effects",
                                       description="Effects turn off by themselves in game mode and on battery.")
        effects.add(rows.switch_row(store, "appearance.blur", "Blur", "Frosted glass behind see-through windows"))
        effects.add(rows.spin_row(store, "appearance.blur_size", "Blur strength", lower=1, upper=12))
        effects.add(rows.switch_row(store, "appearance.shadow", "Shadows"))
        effects.add(rows.spin_row(store, "appearance.inactive_opacity", "Inactive window opacity",
                                  "1.0 = solid", lower=0.5, upper=1.0, step=0.05, digits=2))
        effects.add(rows.switch_row(store, "appearance.dim_inactive", "Dim inactive windows"))
        effects.add(rows.spin_row(store, "appearance.terminal_opacity", "Terminal opacity",
                                  lower=0.5, upper=1.0, step=0.05, digits=2))
        page.add(effects)

        style = Adw.PreferencesGroup(title="Icons, cursor and font")
        style.add(rows.combo_row(store, "appearance.icon_theme", "Icons",
                                 [("Papirus-Dark", "Papirus Dark"), ("Papirus", "Papirus"),
                                  ("Papirus-Light", "Papirus Light"), ("Adwaita", "Adwaita")]))
        style.add(rows.spin_row(store, "appearance.cursor_size", "Cursor size", lower=16, upper=64, step=4))
        style.add(rows.entry_row(store, "appearance.font", "App font (name and size)"))
        page.add(style)

        self.widget = page

    def _apply_preset(self, _button, name):
        for key, value in PRESETS[name].items():
            self.ctx.store.set(f"appearance.{key}", value)
        self.ctx.toast(f"{name} look applied")
