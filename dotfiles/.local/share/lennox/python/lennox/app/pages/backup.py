"""Backup: keep your Lennox setup safe somewhere that survives a reinstall."""

import json
import os
import time

from gi.repository import Adw, Gio, GLib, Gtk

from .. import rows
from ..util import lennox_bin, run_async


def drive_suggestions():
    """Mounted Windows drives and USB sticks: good homes for a backup."""
    found = []
    try:
        with open("/proc/self/mounts", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                where, kind = parts[1].replace("\\040", " "), parts[2]
                if kind in ("ntfs3", "ntfs", "fuseblk", "exfat", "vfat") and \
                        where.startswith(("/run/media/", "/media/", "/mnt/")):
                    found.append(where)
    except OSError:
        pass
    return found


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        where = Adw.PreferencesGroup(
            title="Backup",
            description="Your Lennox settings, your tweaks, alarms and timers, focus and sleep stats and "
                        "the current wallpaper, in one small file. Keep it on the Windows drive, a USB stick "
                        "or a cloud folder: after a reinstall, run the installer with --restore FILE, or "
                        "press Restore below.")
        self.folder_row = Adw.ActionRow(title="Backup folder", subtitle="Not chosen yet")
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", lambda _b: self._choose())
        self.folder_row.add_suffix(choose)
        self.folder_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        where.add(self.folder_row)
        self.drives = []
        for drive in drive_suggestions():
            target = os.path.join(drive, "Lennox backups")
            row = rows.button_row(f"Use {os.path.basename(drive) or drive}", target, "Use",
                                  lambda t=target: self._set_folder(t), "drive-harddisk-symbolic")
            where.add(row)
        where.add(rows.switch_row(store, "backup.weekly", "Back up every week",
                                  "Quietly, when the folder's drive is connected"))
        where.add(rows.spin_row(store, "backup.keep", "Backups to keep", None, lower=1, upper=50, step=1))
        self.now_button = Gtk.Button(label="Back up now", valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
        self.now_button.connect("clicked", lambda _b: self._backup_now())
        now_row = Adw.ActionRow(title="Back up now")
        now_row.add_suffix(self.now_button)
        where.add(now_row)
        page.add(where)

        self.list_group = Adw.PreferencesGroup(title="Your backups")
        self.list_rows = []
        page.add(self.list_group)
        self.widget = page

    def refresh(self):
        folder = self.ctx.store.get("backup.folder")
        self.folder_row.set_subtitle(GLib.markup_escape_text(folder) if folder else "Not chosen yet")
        self.now_button.set_sensitive(bool(folder))
        run_async([lennox_bin("lennox-backup"), "list", "--json"], self._got_list)

    def _set_folder(self, path):
        self.ctx.store.set("backup.folder", path)
        self.ctx.toast(f"Backups go to {path}")
        self.refresh()

    def _choose(self):
        dialog = Gtk.FileDialog(title="Choose where backups go")

        def chosen(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if isinstance(folder, Gio.File) and folder.get_path():
                self._set_folder(folder.get_path())

        dialog.select_folder(self.ctx.window, None, chosen)

    def _backup_now(self):
        self.now_button.set_sensitive(False)

        def done(ok, out, err):
            self.now_button.set_sensitive(True)
            self.ctx.toast(f"Backed up: {os.path.basename(out.strip())}" if ok
                           else (err.strip().splitlines() or ["Backup failed"])[-1], timeout=5)
            self.refresh()

        run_async([lennox_bin("lennox-backup"), "now"], done)

    def _got_list(self, ok, out, _err):
        for row in self.list_rows:
            self.list_group.remove(row)
        self.list_rows = []
        try:
            found = json.loads(out) if ok else []
        except ValueError:
            found = []
        if not found:
            row = Adw.ActionRow(title="No backups yet" if self.ctx.store.get("backup.folder")
                                else "Choose a folder first")
            self.list_group.add(row)
            self.list_rows.append(row)
            return
        for item in found:
            when = time.strftime("%A %-d %B %Y, %H:%M", time.localtime(item.get("time", 0)))
            row = Adw.ActionRow(title=when, subtitle=GLib.markup_escape_text(
                f"Lennox {item.get('version', '?')} · {item.get('computer', '')} · "
                f"{len(item.get('files') or [])} files" + (" + wallpaper" if item.get("wallpaper") else "")))
            button = Gtk.Button(label="Restore", valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda _b, p=item["path"], w=when: self._confirm_restore(p, w))
            row.add_suffix(button)
            self.list_group.add(row)
            self.list_rows.append(row)

    def _confirm_restore(self, path, when):
        dialog = Adw.AlertDialog(
            heading="Restore this backup?",
            body=f"Your settings, tweaks, alarms and stats go back to how they were on {when}. "
                 "Everything is re-applied right after.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("restore", "Restore")
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def chosen(_d, response):
            if response != "restore":
                return

            def done(ok, _out, err):
                if ok:
                    self.ctx.store.reload()
                self.ctx.toast("Restored" if ok else (err.strip().splitlines() or ["Restore failed"])[-1])

            run_async([lennox_bin("lennox-backup"), "restore", path], done)

        dialog.connect("response", chosen)
        dialog.present(self.ctx.window)
