"""Profile: your name and picture, used by the login screen, the lock screen, the welcome
animation and the session screen."""

import os

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async

FACE = os.path.expanduser("~/.face")
AVATARS = [("initials", "Initials"), ("cat", "Cat"), ("orbit", "Orbit"), ("palm", "Palm"), ("blocky", "Blocky")]


def texture(path):
    try:
        return Gdk.Texture.new_from_filename(path)
    except GLib.Error:
        return None


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        self.page = Adw.PreferencesPage()

        top = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER, margin_bottom=6)
        self.avatar = Adw.Avatar(size=128, show_initials=True)
        self.name_label = Gtk.Label(css_classes=["title-1"])
        hint = Gtk.Label(label="Shown on the login screen, the lock screen, the welcome and the session screen",
                         css_classes=["dim-label"], wrap=True, justify=Gtk.Justification.CENTER)
        for w in (self.avatar, self.name_label, hint):
            box.append(w)
        top.add(box)
        self.page.add(top)

        who = Adw.PreferencesGroup(title="Your name")
        who.add(rows.entry_row(store, "profile.name", "What Lennox calls you (empty: your account's name)",
                               validate=lambda t: "40 letters at most" if len(t) > 40 else None,
                               on_applied=lambda ok, _t: ok and self._repaint_if_initials()))
        self.page.add(who)

        pics = Adw.PreferencesGroup(title="Picture", description="Pick a painted one or use your own photo.")
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5,
                                min_children_per_line=3, column_spacing=12, row_spacing=12, homogeneous=True)
        self.tiles = {}
        for kind, title in AVATARS:
            image = Gtk.Image(pixel_size=72)
            label = Gtk.Label(label=title, css_classes=["caption"])
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            inner.append(image)
            inner.append(label)
            button = Gtk.Button(child=inner, css_classes=["flat"], tooltip_text=f"Use {title}")
            button.connect("clicked", lambda _b, k=kind: self._use(k))
            self.flow.append(button)
            self.tiles[kind] = (button, image, label, title)
        pics.add(self.flow)
        pics.add(rows.button_row("Your own picture", "Any photo; it is cropped to a square", "Choose…",
                                 self._choose, "image-x-generic-symbolic", suggested=True))
        self.page.add(pics)

        self.widget = self.page
        self.refresh()

    # ------------------------------------------------------------ showing

    def refresh(self):
        self.name_label.set_label(self._name())
        self.avatar.set_text(self._name())
        tex = texture(FACE) if os.path.exists(FACE) else None
        self.avatar.set_custom_image(tex)
        current = self.ctx.store.get("profile.picture")
        for kind, (_button, _image, label, title) in self.tiles.items():
            label.set_label(f"✓ {title}" if kind == current else title)
        run_async([lennox_bin("lennox-profile"), "previews"], self._got_previews)

    def _name(self):
        store = self.ctx.store
        for path in ("profile.name", "greeting.name"):
            value = str(store.get(path) or "").strip()
            if value:
                return value
        return GLib.get_real_name() if GLib.get_real_name() not in ("", "Unknown") else GLib.get_user_name().capitalize()

    def _got_previews(self, ok, out, _err):
        if not ok:
            return
        for line in out.splitlines():
            kind, _, path = line.partition("\t")
            if kind in self.tiles and os.path.exists(path):
                self.tiles[kind][1].set_from_paintable(texture(path))

    # ------------------------------------------------------------ changing

    def _done(self, ok, _out, err):
        if not ok:
            self.ctx.toast(f"Could not change the picture: {err.strip()[:120]}")
        self.refresh()

    def _use(self, kind):
        run_async([lennox_bin("lennox-profile"), "avatar", kind], self._done)

    def _repaint_if_initials(self):
        if self.ctx.store.get("profile.picture") == "initials":
            run_async([lennox_bin("lennox-profile"), "avatar", "initials"], self._done)
        else:
            self.refresh()

    def _choose(self):
        dialog = Gtk.FileDialog(title="Choose a picture")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        images = Gtk.FileFilter(name="Pictures")
        images.add_mime_type("image/*")
        filters.append(images)
        dialog.set_filters(filters)
        dialog.open(self.ctx.window, None, self._picked)

    def _picked(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file is not None and file.get_path():
            run_async([lennox_bin("lennox-profile"), "picture", file.get_path()], self._done)
