"""Settings > Widgets: how each island activity looks (its icon and glow color)."""

from gi.repository import Gdk, Gio, Gtk

from ..widgets import island as I
from ..widgets.style import load_colors

GLOW = {"amber": "#ff9f0a", "green": "#30d158", "red": "#ff453a", "blue": "#0a84ff"}
# (name, icon, kind): kind picks the glow like the island does
ACTIVITIES = [
    ("Music", "audio-x-generic-symbolic", "music"), ("Timer", "timer-symbolic", "timer"),
    ("Alarm", "alarm-symbolic", "ringing"), ("Reminder", "appointment-soon-symbolic", "timer"),
    ("Focus", "find-location-symbolic", "focus"), ("Break", "face-smile-symbolic", "focus"),
    ("Call", "audio-input-microphone-symbolic", "call"), ("Stopwatch", "stopwatch-symbolic", "stopwatch"),
    ("Recording", "media-record-symbolic", "event"), ("Charging", "battery-full-charging-symbolic", "event"),
    ("Notification", "mail-unread-symbolic", "event"), ("Volume", "audio-volume-high-symbolic", "event"),
    ("Wi-Fi", "network-wireless-symbolic", "event"), ("Bluetooth", "bluetooth-active-symbolic", "event"),
]
_provider = None


def color(kind, icon, accent):
    glow = I.glow_for(kind, {"icon": icon}) or "accent"
    return accent if glow == "accent" else GLOW[glow]


def preview():
    """A wrap of little black island pills, one per activity."""
    global _provider
    accent = load_colors()["primary"]
    css = [".il-pill { background: #000; color: #fff; border-radius: 99px; padding: 5px 11px 5px 9px; "
           "font-weight: 600; font-size: 12px; }"]
    box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6,
                      max_children_per_line=7, homogeneous=False, valign=Gtk.Align.START)
    for i, (name, icon, kind) in enumerate(ACTIVITIES):
        c = color(kind, icon, accent)
        css.append(f".il-{i} {{ border: 1px solid alpha({c}, 0.65); box-shadow: inset 0 0 8px alpha({c}, 0.30); }}"
                   f" .il-{i} image {{ color: {c}; }}")
        pill = Gtk.Box(spacing=6, css_classes=["il-pill", f"il-{i}"], halign=Gtk.Align.START,
                       valign=Gtk.Align.START)
        gicon = I.island_icon(icon)
        image = Gtk.Image.new_from_gicon(gicon) if isinstance(gicon, Gio.Icon) else Gtk.Image.new_from_icon_name(gicon)
        image.set_pixel_size(14)
        pill.append(image)
        pill.append(Gtk.Label(label=name))
        box.append(pill)
    display = Gdk.Display.get_default()
    if display is not None:
        if _provider is None:
            _provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _provider.load_from_string("\n".join(css))
    return box
