"""Window overview (SUPER + TAB): every window on every workspace, with previews.

Type to search, arrows to move, Enter or a click to jump there, Esc to close.
Windows on screen get a fresh preview; the others show how they looked the
last time the overview saw them (or their app icon).
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys

LAYER_SHELL = False
if not os.environ.get("LENNOX_WIDGETS_NO_LAYER"):
    for _lib in ("libgtk4-layer-shell.so", "libgtk4-layer-shell.so.0"):
        try:
            ctypes.CDLL(_lib)                 # before GTK loads libwayland-client
            LAYER_SHELL = True
            break
        except OSError:
            pass

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

if LAYER_SHELL:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LS  # noqa: E402
    except (ValueError, ImportError):
        LAYER_SHELL = False

APP_ID = "dev.lennox.Overview"
THUMBS = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "lennox", "thumbs")
MINIMIZED = "special:minimized"
CARD_W, CARD_H = 260, 160

CSS = """
window.lennox-overview { background: alpha(black, 0.55); }
.overview-search { min-height: 40px; font-size: 16px; border-radius: 12px; min-width: 420px; }
.overview-hint { color: alpha(white, 0.6); font-size: 12px; }
.overview-ws { color: white; font-weight: 700; font-size: 14px; margin: 14px 0 4px 6px; }
.overview-card { background: alpha(white, 0.08); border-radius: 14px; padding: 8px; border: 2px solid transparent; }
.overview-card:hover { background: alpha(white, 0.14); }
flowboxchild:selected .overview-card, flowboxchild:focus .overview-card { border-color: @accent_color; }
flowboxchild { padding: 0; background: none; outline: none; }
.overview-thumb { border-radius: 9px; background: alpha(black, 0.35); }
.overview-title { color: white; font-size: 12px; }
.overview-min { color: alpha(white, 0.55); font-size: 11px; }
.overview-empty { color: alpha(white, 0.7); font-size: 15px; margin-top: 60px; }
"""


# ---------------------------------------------------------------- the pure part (tested)

def workspace_label(ws):
    name = (ws or {}).get("name") or ""
    if name == MINIMIZED:
        return "Minimized"
    if name.startswith("special:"):
        return name.split(":", 1)[1].capitalize() or "Special"
    return f"Workspace {name or ws.get('id', '?')}"


def matches(client, query):
    words = query.lower().split()
    hay = " ".join([client.get("class") or "", client.get("initialClass") or "", client.get("title") or ""]).lower()
    return all(w in hay for w in words)


def group(clients, query=""):
    """[(label, [client...])]: numbered workspaces in order, then special ones, minimized last."""
    groups = {}
    for c in clients:
        if not c.get("mapped", True) or not c.get("class") and not c.get("title"):
            continue
        if query and not matches(c, query):
            continue
        groups.setdefault(json.dumps(c.get("workspace") or {}, sort_keys=True), []).append(c)

    def order(item):
        ws = json.loads(item[0])
        name = ws.get("name") or ""
        if name == MINIMIZED:
            return (2, 0, name)
        if name.startswith("special:"):
            return (1, 0, name)
        return (0, ws.get("id", 0), name)

    out = []
    for key, members in sorted(groups.items(), key=order):
        members.sort(key=lambda c: c.get("focusHistoryID", 99))
        out.append((workspace_label(json.loads(key)), members))
    return out


def visible_workspaces(monitors):
    return {m.get("activeWorkspace", {}).get("id") for m in monitors}


# ---------------------------------------------------------------- Hyprland

def hypr(*args):
    try:
        out = subprocess.run(["hyprctl", *args, "-j"], capture_output=True, text=True, timeout=3, check=False).stdout
        return json.loads(out)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []


def dispatch(text):
    subprocess.run(["hyprctl", "dispatch", text], capture_output=True, check=False)


def thumb_path(client):
    return os.path.join(THUMBS, client["address"].replace("0x", "") + ".jpg")


def capture(clients, monitors):
    """Fresh previews of the windows on screen (before the overview covers them)."""
    if not shutil.which("grim"):
        return
    os.makedirs(THUMBS, exist_ok=True)
    shown = visible_workspaces(monitors)
    jobs = []
    for c in clients:
        ws = c.get("workspace") or {}
        if ws.get("id") not in shown or c.get("hidden") or not c.get("size"):
            continue
        (x, y), (w, h) = c["at"], c["size"]
        if w < 20 or h < 20:
            continue
        scale = min(1.0, 520 / max(w, 1))
        try:
            jobs.append(subprocess.Popen(["grim", "-g", f"{x},{y} {w}x{h}", "-s", f"{scale:.2f}", "-t", "jpeg",
                                          "-q", "80", thumb_path(c)],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        except OSError:
            break
    for job in jobs:
        try:
            job.wait(timeout=2)
        except subprocess.TimeoutExpired:
            job.kill()
    # Forget previews of windows that are gone
    alive = {thumb_path(c) for c in clients}
    for name in os.listdir(THUMBS):
        path = os.path.join(THUMBS, name)
        if path not in alive:
            try:
                os.remove(path)
            except OSError:
                pass


def preview(path):
    """The preview scaled to fit a card, as a texture (None if there isn't one)."""
    if not os.path.exists(path):
        return None
    try:
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, CARD_W, CARD_H, True)
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except (GLib.Error, ValueError, ImportError):
        return None


def app_icon(client):
    for name in (client.get("class"), client.get("initialClass")):
        if not name:
            continue
        for candidate in (name, name.lower()):
            try:
                info = Gio.DesktopAppInfo.new(candidate + ".desktop")
            except TypeError:
                info = None
            if info and info.get_icon():
                return info.get_icon()
        try:
            results = Gio.DesktopAppInfo.search(name)
        except GLib.Error:
            results = []
        for group_ in results:
            for desktop_id in group_:
                info = Gio.DesktopAppInfo.new(desktop_id)
                if info and info.get_icon():
                    return info.get_icon()
    return Gio.ThemedIcon.new("application-x-executable")


# ---------------------------------------------------------------- the window

class Overview(Gtk.ApplicationWindow):
    def __init__(self, app, clients):
        super().__init__(application=app, title="Overview", css_classes=["lennox-overview"])
        self.clients = clients
        if LAYER_SHELL and LS.is_supported():
            LS.init_for_window(self)
            LS.set_namespace(self, "lennox-overview")
            LS.set_layer(self, LS.Layer.OVERLAY)
            LS.set_keyboard_mode(self, LS.KeyboardMode.EXCLUSIVE)
            LS.set_exclusive_zone(self, -1)
            for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
                LS.set_anchor(self, edge, True)
        else:
            monitors = Gdk.Display.get_default().get_monitors()
            if monitors.get_n_items():
                geometry = monitors.get_item(0).get_geometry()
                self.set_default_size(geometry.width, geometry.height)
            self.fullscreen()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=40, margin_bottom=30,
                        margin_start=60, margin_end=60)
        self.search = Gtk.SearchEntry(placeholder_text="Search windows", halign=Gtk.Align.CENTER,
                                      css_classes=["overview-search"])
        self.search.connect("search-changed", lambda _e: self.build())
        self.search.connect("activate", lambda _e: self.open_first())
        self.search.connect("stop-search", lambda _e: self.close())
        outer.append(self.search)
        outer.append(Gtk.Label(label="Type to search · arrows and Enter · click a window to go there · Esc closes",
                               css_classes=["overview-hint"]))
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        outer.append(self.scroll)
        self.set_child(outer)
        self.search.set_key_capture_widget(self)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        # A click on the empty background closes it
        click = Gtk.GestureClick()
        click.connect("released", self._background_click)
        self.scroll.add_controller(click)
        self.first = None
        self.build()

    def _key(self, _ctl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _background_click(self, gesture, _n, x, y):
        picked = self.scroll.pick(x, y, Gtk.PickFlags.DEFAULT)
        while picked is not None and picked is not self.scroll:
            if isinstance(picked, Gtk.FlowBoxChild):
                return
            picked = picked.get_parent()
        self.close()

    def build(self):
        query = self.search.get_text().strip()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.first = None
        groups = group(self.clients, query)
        if not groups:
            box.append(Gtk.Label(label="No windows match" if query else "No windows open",
                                 css_classes=["overview-empty"]))
        for label, members in groups:
            box.append(Gtk.Label(label=label, xalign=0, css_classes=["overview-ws"]))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True, max_children_per_line=6,
                               min_children_per_line=1, column_spacing=14, row_spacing=14, halign=Gtk.Align.START,
                               activate_on_single_click=True)
            flow.connect("child-activated", lambda _f, child: self.open(child.client))
            for c in members:
                child = Gtk.FlowBoxChild()
                child.client = c
                child.set_child(self.card(c))
                flow.append(child)
                if self.first is None:
                    self.first = c
            box.append(flow)
        self.scroll.set_child(box)

    def card(self, c):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["overview-card"])
        thumb = Gtk.Box(css_classes=["overview-thumb"], overflow=Gtk.Overflow.HIDDEN)
        thumb.set_size_request(CARD_W, CARD_H)
        path = thumb_path(c)
        texture = preview(path)
        if texture is not None:
            # Scaled to the card first: a Picture asks for its image's full size
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_hexpand(True)
            thumb.append(picture)
        else:
            icon = Gtk.Image.new_from_gicon(app_icon(c))
            icon.set_pixel_size(64)
            icon.set_hexpand(True)
            icon.set_vexpand(True)
            thumb.append(icon)
        card.append(thumb)
        row = Gtk.Box(spacing=6)
        small = Gtk.Image.new_from_gicon(app_icon(c))
        small.set_pixel_size(16)
        row.append(small)
        title = c.get("title") or c.get("class") or "Window"
        row.append(Gtk.Label(label=title, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
                             max_width_chars=28, css_classes=["overview-title"]))
        if (c.get("workspace") or {}).get("name") == MINIMIZED:
            row.append(Gtk.Label(label="minimized", css_classes=["overview-min"]))
        card.append(row)
        card.set_tooltip_text(f"{c.get('class', '')}: {title}")
        return card

    def open_first(self):
        if self.first is not None:
            self.open(self.first)

    def open(self, client):
        address = client.get("address", "")
        self.close()
        if (client.get("workspace") or {}).get("name") == MINIMIZED:
            subprocess.Popen([os.path.expanduser("~/.local/bin/lennox-minimize"), "restore", address])
        elif address.startswith("0x"):
            dispatch(f'hl.dsp.focus({{ window = "address:{address}" }})')


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None

    def do_activate(self):
        if self.window is not None:          # SUPER + TAB again closes it
            self.window.close()
            return
        clients = hypr("clients")
        capture(clients, hypr("monitors"))
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Overview(self, clients)
        self.window.connect("close-request", self._closed)
        self.window.present()
        self.window.search.grab_focus()

    def _closed(self, _w):
        self.window = None
        return False


def main(argv):
    return App().run(argv[:1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
