"""Bar style gallery: a small live mock-up of every bar style, drawn with GTK in
the wallpaper's current colors. Click one to use it."""

from gi.repository import Gdk, Gtk

from ..widgets.style import load_colors

_provider = None

CSS = """
.bp-card {{ padding: 8px; border-radius: 14px; }}
.bp-card.bp-selected {{ outline: 2px solid {primary}; outline-offset: -2px; }}
.bp-wall {{
    border-radius: 10px; padding: 7px 8px 30px 8px;
    background-image: linear-gradient(135deg, {primary_container}, {surface} 55%, {secondary_container});
}}
.bp-bar {{ color: {on_surface}; font-size: 9px; font-weight: 600; min-height: 22px; }}
.bp-bar label {{ font-size: 9px; }}
.bp-bar image {{ -gtk-icon-size: 10px; }}
.bp-inner {{ padding: 0 3px; border-radius: 10px; }}
.bp-group {{ padding: 0 4px; border-radius: 99px; }}
.bp-launch {{ min-width: 14px; min-height: 14px; border-radius: 99px; background: {primary}; margin: 0 3px 0 0; }}
.bp-ws {{ min-width: 5px; min-height: 5px; border-radius: 99px; background: alpha({on_surface}, 0.30); margin: 0 1px; }}
.bp-ws label {{ font-size: 7px; font-weight: 800; color: {on_primary}; }}
.bp-ws.active {{ min-width: 18px; min-height: 12px; background: {primary}; }}
.bp-mod {{ padding: 0 4px; border-radius: 99px; }}
.bp-chip {{ border-radius: 99px; padding: 1px 3px; }}

/* Islands: three floating glass islands */
.bp-lennox .bp-group {{ background: alpha({surface_container}, 0.80); border: 1px solid alpha({outline_variant}, 0.6); min-height: 20px; }}
/* Line: one slim strip */
.bp-lennox-line .bp-inner {{ background: alpha({surface_container}, 0.80); border: 1px solid alpha({outline_variant}, 0.6); }}
/* Aurora: a strip with a glowing gradient edge */
.bp-lennox-aurora {{ padding: 1px; border-radius: 11px; background-image: linear-gradient(100deg, {primary}, {tertiary}, {secondary}); }}
.bp-lennox-aurora .bp-inner {{ background: alpha({surface_container}, 0.92); box-shadow: inset 0 1px alpha({on_surface}, 0.10); }}
.bp-lennox-aurora .bp-ws.active {{ background-image: linear-gradient(90deg, {primary}, {tertiary}); }}
/* Pills: every module its own pill, icons on colored chips */
.bp-lennox-pills .bp-mod, .bp-lennox-pills .bp-start, .bp-lennox-pills .bp-clock {{
    background: alpha({surface_container}, 0.85); border: 1px solid alpha({outline_variant}, 0.6);
    border-radius: 99px; margin: 0 1px; min-height: 20px; padding: 0 4px 0 2px;
}}
.bp-lennox-pills .bp-clock {{ padding: 0 7px; }}
.bp-lennox-pills .chip-a {{ background: alpha({primary}, 0.35); }}
.bp-lennox-pills .chip-b {{ background: alpha({tertiary}, 0.35); }}
.bp-lennox-pills .chip-c {{ background: alpha({secondary}, 0.35); }}
/* Minimal Dots: thin, see-through, quiet */
.bp-lennox-dots {{ min-height: 17px; }}
.bp-lennox-dots .bp-inner {{ background: alpha({surface_container}, 0.40); border: 1px solid alpha({outline_variant}, 0.3); }}
.bp-lennox-dots, .bp-lennox-dots label {{ color: alpha({on_surface}, 0.65); font-size: 8px; }}
.bp-lennox-dots .bp-launch {{ background: transparent; border: 2px solid {primary}; min-width: 6px; min-height: 6px; }}
.bp-lennox-dots .bp-ws.active {{ min-height: 5px; min-width: 12px; }}
.bp-lennox-dots .bp-ws.active label {{ color: transparent; font-size: 1px; }}
/* The classic ML4W styles */
.bp-modern .bp-inner {{ background: {surface_container}; border-radius: 0; }}
.bp-glass .bp-inner {{ background: alpha(white, 0.14); border: 1px solid alpha(white, 0.25); border-radius: 8px; }}
.bp-minimal .bp-launch {{ background: transparent; }}
"""


def install_css(colors=None):
    """(Re)load the gallery's CSS with the wallpaper's colors."""
    global _provider
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _provider.load_from_string(CSS.format(**(colors or load_colors())))


def _box(css, *children, spacing=0, **kw):
    kw.setdefault("valign", Gtk.Align.CENTER)
    box = Gtk.Box(spacing=spacing, css_classes=css, **kw)
    for child in children:
        box.append(child)
    return box


def _module(icon, text, chip):
    image = Gtk.Image.new_from_icon_name(icon)
    return _box(["bp-mod"], _box(["bp-chip", chip], image), Gtk.Label(label=text), spacing=3)


def mock_bar(style):
    """A small bar in this style: Lennox button + workspaces, the clock, status icons."""
    dots = []
    for n in range(1, 6):
        ws = Gtk.Box(css_classes=["bp-ws"] + (["active"] if n == 2 else []), valign=Gtk.Align.CENTER)
        if n == 2:
            ws.append(Gtk.Label(label="2", hexpand=True))     # centred in the pill
            ws.set_hexpand(False)
        dots.append(ws)
    left = _box(["bp-group", "bp-start"], Gtk.Box(css_classes=["bp-launch"], valign=Gtk.Align.CENTER), *dots)
    center = _box(["bp-group", "bp-clock"], Gtk.Label(label="16:40"))
    right = _box(["bp-group"], _module("audio-volume-high-symbolic", "45%", "chip-a"),
                 _module("network-wireless-symbolic", "80%", "chip-b"),
                 _module("battery-good-symbolic", "72%", "chip-c"), spacing=2)
    inner = Gtk.CenterBox(css_classes=["bp-inner"], hexpand=True)
    inner.set_start_widget(left)
    inner.set_center_widget(center)
    inner.set_end_widget(right)
    return _box(["bp-bar", f"bp-{style}"], inner, valign=Gtk.Align.START)


class Gallery:
    """A grid of cards, one per style; the one in use is outlined."""

    def __init__(self, store, styles, path="bar.style"):
        install_css()
        self.store, self.path = store, path
        self.cards = {}
        self.widget = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, max_children_per_line=2,
                                  min_children_per_line=2, column_spacing=10, row_spacing=10)
        for value, label in styles:
            name, _, about = label.partition(": ")
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=6)
            text.append(Gtk.Label(label=name, xalign=0, css_classes=["heading"]))
            text.append(Gtk.Label(label=about or " ", xalign=0, wrap=True, css_classes=["dim-label", "caption"]))
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            content.append(_box(["bp-wall"], mock_bar(value), orientation=Gtk.Orientation.VERTICAL))
            content.append(text)
            card = Gtk.Button(child=content, css_classes=["card", "bp-card"], tooltip_text=f"Use {name}")
            card.connect("clicked", lambda _b, v=value: store.set(path, v))
            self.cards[value] = card
            self.widget.append(card)
        store.connect("changed", lambda _s, changed: changed == path and self.mark())
        self.mark()

    def mark(self):
        current = self.store.get(self.path)
        for value, card in self.cards.items():
            (card.add_css_class if value == current else card.remove_css_class)("bp-selected")
