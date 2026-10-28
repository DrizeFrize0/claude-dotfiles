"""Wallpaper: pick one from a grid; the whole desktop re-colors to match."""

import hashlib
import os
import threading

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from ... import settings as S  # noqa: E402
from .. import rows  # noqa: E402
from ..util import HOME, launch, lennox_bin, read_file, run_async  # noqa: E402

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "lennox")
THUMBS = os.path.join(CACHE, "thumbnails")
CURRENT = os.path.join(CACHE, "wallpaper", "current")
THUMB_W, THUMB_H = 400, 250

TRANSITIONS = [("grow", "Grow from a point"), ("center", "Grow from the center"), ("outer", "Shrink inwards"),
               ("wipe", "Wipe"), ("wave", "Wave"), ("fade", "Fade"), ("any", "Random spot"), ("none", "Instant")]
BLURS = [("0x0", "No blur"), ("20x10", "Light"), ("50x30", "Medium (ML4W)"), ("80x50", "Strong")]


def thumbnail_path(image):
    # Same naming as lennox-menu (md5 of the path), so both share the cache
    return os.path.join(THUMBS, hashlib.md5(image.encode()).hexdigest() + ".png")


def make_thumbnail(image):
    target = thumbnail_path(image)
    if os.path.exists(target):
        return target
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(image)
        scale = max(THUMB_W / pixbuf.get_width(), THUMB_H / pixbuf.get_height())
        width, height = max(1, int(pixbuf.get_width() * scale)), max(1, int(pixbuf.get_height() * scale))
        scaled = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        x, y = (width - THUMB_W) // 2, (height - THUMB_H) // 2
        cropped = scaled.new_subpixbuf(max(0, x), max(0, y), min(THUMB_W, width), min(THUMB_H, height))
        os.makedirs(THUMBS, exist_ok=True)
        cropped.savev(target, "png", [], [])
        return target
    except GLib.Error:
        return None


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.loaded_folder = None
        self.generation = 0
        store = ctx.store

        page = Adw.PreferencesPage()

        actions = Adw.PreferencesGroup(title="Your wallpapers",
                                       description="Click one to set it. Shortcuts: SUPER + W picker, SUPER + SHIFT + W random.")
        header = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        random_button = Gtk.Button(label="Surprise me")
        random_button.add_css_class("suggested-action")
        random_button.add_css_class("pill")
        random_button.connect("clicked", lambda _b: self._set(None))
        folder_button = Gtk.Button(label="Open folder")
        folder_button.add_css_class("pill")
        folder_button.connect("clicked", lambda _b: launch(["xdg-open", self._folder()]))
        header.append(random_button)
        header.append(folder_button)
        actions.set_header_suffix(header)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=2, max_children_per_line=5,
                                column_spacing=10, row_spacing=10, activate_on_single_click=True)
        self.flow.connect("child-activated", self._on_activated)
        self.empty = Adw.StatusPage(icon_name="image-missing-symbolic", title="No wallpapers yet",
                                    description="Add pictures to the folder, or choose another folder below.")
        self.empty.set_visible(False)
        actions.add(self.flow)
        actions.add(self.empty)
        page.add(actions)

        options = Adw.PreferencesGroup(title="Options")
        self.folder_row = Adw.ActionRow(title="Wallpaper folder", subtitle=store.get("wallpaper.folder"))
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_folder)
        self.folder_row.add_suffix(choose)
        options.add(self.folder_row)
        options.add(rows.combo_row(store, "wallpaper.transition", "Transition", TRANSITIONS))
        options.add(rows.spin_row(store, "wallpaper.auto_change_minutes", "Change automatically every",
                                  "Minutes, 0 = never", lower=0, upper=1440, step=5))
        options.add(rows.combo_row(store, "wallpaper.lockscreen_blur", "Lock screen blur", BLURS,
                                   on_change=lambda _v: self._set(self._current(), quiet=True)))
        paint = Adw.ActionRow(title="Lennox wallpaper pack",
                              subtitle="12 wallpapers painted on your laptop: aurora, sunset beach, night sky, dunes, clouds…")
        paint.add_prefix(Gtk.Image.new_from_icon_name("applications-graphics-symbolic"))
        paint_button = Gtk.Button(label="Paint", valign=Gtk.Align.CENTER)
        paint_button.connect("clicked", self._paint_pack)
        paint.add_suffix(paint_button)
        options.add(paint)
        options.add(rows.button_row("ML4W wallpaper collection", "Download 200+ more wallpapers (a big download)",
                                    "Download", self._download_more, "folder-download-symbolic"))
        page.add(options)

        self.widget = page

    # ---------------------------------------------------------------- data

    def _folder(self):
        return S.expand(self.ctx.store.get("wallpaper.folder"))

    def _current(self):
        return read_file(CURRENT).strip()

    def _images(self):
        folder = self._folder()
        found = []
        for root, dirs, files in os.walk(folder):
            depth = root[len(folder):].count(os.sep)
            if depth >= 1:
                dirs[:] = []
            for name in files:
                if name.lower().endswith(EXTENSIONS):
                    found.append(os.path.join(root, name))
        return sorted(found, key=lambda p: os.path.basename(p).lower())

    # ---------------------------------------------------------------- grid

    def refresh(self):
        folder = self._folder()
        if folder == self.loaded_folder:
            self._mark_current()
            return
        self.loaded_folder = folder
        self.generation += 1
        generation = self.generation
        child = self.flow.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.flow.remove(child)
            child = nxt
        images = self._images()
        self.empty.set_visible(not images)
        self.flow.set_visible(bool(images))
        pictures = {}
        for image in images:
            picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            picture.set_size_request(180, 112)
            frame = Gtk.Frame(child=picture)
            frame.add_css_class("card")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.append(frame)
            label = Gtk.Label(label=os.path.splitext(os.path.basename(image))[0], ellipsize=Pango.EllipsizeMode.END, max_width_chars=18)
            label.add_css_class("caption")
            box.append(label)
            flow_child = Gtk.FlowBoxChild(child=box)
            flow_child.image = image
            flow_child.frame = frame
            self.flow.append(flow_child)
            pictures[image] = picture
        self._mark_current()

        def worker():
            for image, picture in pictures.items():
                if generation != self.generation:
                    return
                thumb = make_thumbnail(image)
                if thumb:
                    GLib.idle_add(picture.set_filename, thumb)

        threading.Thread(target=worker, daemon=True).start()

    def _mark_current(self):
        current = self._current()
        child = self.flow.get_first_child()
        while child:
            if getattr(child, "image", None) == current:
                child.frame.add_css_class("accent")
                child.set_tooltip_text("Current wallpaper")
            elif hasattr(child, "frame"):
                child.frame.remove_css_class("accent")
                child.set_tooltip_text(None)
            child = child.get_next_sibling()

    # ---------------------------------------------------------------- actions

    def _on_activated(self, _flow, child):
        self._set(child.image)

    def _set(self, image, quiet=False):
        argv = [lennox_bin("lennox-wallpaper")]
        argv += [image] if image else ["--random"]
        if quiet:
            argv.append("--quiet")
        else:
            self.ctx.toast("Applying the wallpaper and its colors…")

        def done(ok, _out, err):
            if ok:
                if not quiet:
                    self.ctx.toast("Done. Everything matches your new wallpaper.")
            else:
                self.ctx.toast(f"Could not set the wallpaper: {err.strip()[-120:]}", 6)
            self._mark_current()

        run_async(argv, done)

    def _choose_folder(self, _button):
        dialog = Gtk.FileDialog(title="Choose your wallpaper folder", modal=True)
        folder = self._folder()
        if os.path.isdir(folder):
            dialog.set_initial_folder(Gio.File.new_for_path(folder))

        def chosen(d, result):
            try:
                file = d.select_folder_finish(result)
            except GLib.Error:
                return  # cancelled
            if file and file.get_path():
                path = file.get_path()
                if path.startswith(HOME + os.sep):
                    path = "~" + path[len(HOME):]
                self.ctx.store.set("wallpaper.folder", path)
                self.folder_row.set_subtitle(path)
                self.refresh()

        dialog.select_folder(self.ctx.window, None, chosen)

    def _download_more(self):
        launch(["kitty", "--class", "lennox-floating", "--title", "Downloading wallpapers", "--hold",
                lennox_bin("lennox-wallpapers"), "ml4w"])
        self.loaded_folder = None

    def _paint_pack(self, button):
        button.set_sensitive(False)
        button.set_label("Painting…")
        self.ctx.toast("Painting the Lennox wallpapers (about half a minute)")

        def done(ok, _out, err):
            button.set_sensitive(True)
            button.set_label("Paint")
            if ok:
                self.loaded_folder = None
                self.refresh()
                self.ctx.toast("The Lennox wallpapers are ready")
            else:
                self.ctx.toast("Could not paint the wallpapers: " + (err.strip().splitlines() or ["unknown error"])[-1])
        run_async([lennox_bin("lennox-wallpapers"), "make"], done)
