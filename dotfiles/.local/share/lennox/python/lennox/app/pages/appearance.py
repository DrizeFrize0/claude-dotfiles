"""Appearance: dark/light, colors, animations, windows."""

from gi.repository import Adw, Gdk, Gtk

from ... import settings as S
from .. import rows

SCHEMES = [
    ("scheme-tonal-spot", "Calm (default)"),
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
    ("dynamic", "Dynamic (spinning border)"),
    ("moving", "Moving"),
    ("classic", "Classic"),
    ("fast", "Fast"),
    ("smooth", "Smooth"),
    ("bouncy", "Bouncy"),
    ("off", "Off"),
]

BORDERS = [
    ("gradient", "Gradient (ML4W)"),
    ("animated", "Animated gradient"),
    ("solid", "Solid"),
    ("none", "None"),
]

WORKSPACE_ANIMS = [
    ("preset", "Same as Animations"),
    ("slide", "Slide sideways"),
    ("slidevert", "Slide up and down"),
    ("fade", "Fade"),
    ("slidefade", "Slide and fade"),
]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        colors = Adw.PreferencesGroup(title="Colors",
                                      description="Pick a color theme, or let your wallpaper choose the colors.")
        colors.add(self._theme_picker(store))
        colors.add(rows.combo_row(store, "appearance.color_mode", "Mode",
                                  [("dark", "Dark"), ("light", "Light")],
                                  "Shortcut: SUPER + SHIFT + M"))
        colors.add(rows.combo_row(store, "appearance.color_scheme", "Color style", SCHEMES))
        page.add(colors)

        presets = Adw.PreferencesGroup(title="Looks", description="Start from a look, then fine-tune below.")
        box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                          column_spacing=8, row_spacing=8, homogeneous=True)
        for name, (title, description, _values) in S.LOOKS.items():
            button = Gtk.Button(label=title, tooltip_text=description)
            button.add_css_class("pill")
            button.connect("clicked", self._apply_preset, name)
            box.append(button)
        presets.add(box)
        page.add(presets)

        windows = Adw.PreferencesGroup(title="Windows")
        windows.add(rows.combo_row(store, "appearance.animations", "Animations", ANIMATIONS))
        windows.add(rows.combo_row(store, "appearance.workspace_anim", "Workspace switch", WORKSPACE_ANIMS))
        windows.add(rows.combo_row(store, "appearance.border_style", "Border", BORDERS,
                                   "Animated slowly spins the colors (turns off on battery)"))
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

    def _theme_picker(self, store):
        """A row of round color swatches, one per color theme."""
        css = ["button.lennox-swatch { min-width: 38px; min-height: 38px; padding: 0; border-radius: 99px;"
               " border: 2px solid alpha(currentColor, 0.15); box-shadow: none; }",
               "button.lennox-swatch.selected { border: 3px solid @accent_color; }"]
        for tid, (_name, color, _scheme) in S.THEMES.items():
            if color:
                css.append(f"button.lennox-swatch-{tid} {{ background: {color}; }}")
                css.append(f"button.lennox-swatch-{tid}:hover {{ background: mix({color}, white, 0.15); }}")
        provider = Gtk.CssProvider()
        text = "\n".join(css)
        try:
            provider.load_from_string(text)
        except AttributeError:  # GTK < 4.12
            provider.load_from_data(text, -1)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Gtk.Box(spacing=12)
        header.append(Gtk.Label(label="Theme", xalign=0, hexpand=True))
        self.theme_name = Gtk.Label(valign=Gtk.Align.CENTER)
        self.theme_name.add_css_class("dim-label")
        header.append(self.theme_name)
        box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=12, min_children_per_line=6,
                          column_spacing=6, row_spacing=6, valign=Gtk.Align.CENTER, margin_top=8, margin_bottom=8)
        self.swatches = {}
        for tid, (name, color, _scheme) in S.THEMES.items():
            button = Gtk.Button(tooltip_text=name, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
            button.add_css_class("lennox-swatch")
            button.add_css_class(f"lennox-swatch-{tid}")
            if not color:
                button.set_icon_name("image-x-generic-symbolic")
            button.connect("clicked", lambda _b, t=tid: store.set("appearance.theme", t))
            self.swatches[tid] = button
            box.append(button)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          margin_top=12, margin_bottom=6, margin_start=12, margin_end=12)
        content.append(header)
        content.append(box)
        row = Adw.PreferencesRow(activatable=False, focusable=False)
        row.set_child(content)

        def show(_store=None, path="appearance.theme"):
            if path != "appearance.theme":
                return
            current = store.get("appearance.theme")
            for tid, button in self.swatches.items():
                (button.add_css_class if tid == current else button.remove_css_class)("selected")
            self.theme_name.set_label(S.THEMES.get(current, ("",))[0])
        store.connect("changed", lambda st, path: show(st, path))
        show()
        return row

    def _apply_preset(self, _button, name):
        title, _description, values = S.LOOKS[name]
        for path, value in values.items():
            self.ctx.store.set(path, value)
        self.ctx.toast(f"{title} look applied")
