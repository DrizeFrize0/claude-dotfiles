"""Safety: restore points, copies of your files, and the self-heal watcher."""

import json

from gi.repository import Adw

from .. import rows
from ..util import launch, lennox_bin, run_async


def terminal(*command):
    """A small terminal window (sudo and rsync need to show you what they do)."""
    launch(["kitty", "--class", "lennox-floating", "--title", "Lennox", "--hold", *command])


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        self.status = Adw.PreferencesGroup(title="Right now")
        self.rows = {key: rows.info_row(key, "…") for key in ("System restore points", "Files copied to a drive", "Drives found")}
        for row in self.rows.values():
            self.status.add(row)
        page.add(self.status)

        points = Adw.PreferencesGroup(
            title="Restore points",
            description="A snapshot of the whole system. Every update takes one first, so a bad update can be taken back. "
                        "The boot menu also starts from any of them (Arch Linux snapshots). Needs btrfs, which the installer sets up.")
        points.add(rows.switch_row(store, "safety.snapshot_on_upgrade", "One before every Lennox upgrade"))
        points.add(rows.button_row("Take one now", "Before you try something risky", "Take", lambda: terminal(lennox_bin("lennox-safety"), "snap"),
                                   "document-save-symbolic"))
        points.add(rows.button_row("Undo the last update", "Puts back what it changed on the system (not your files), then restart",
                                   "Undo…", lambda: terminal(lennox_bin("lennox-safety"), "undo"), "edit-undo-symbolic"))
        page.add(points)

        files = Adw.PreferencesGroup(
            title="Your files",
            description="Copies your folders to a USB stick or the Windows drive. Nothing is ever deleted there; caches are skipped. "
                        "After a reinstall, Restore puts everything back, including your private SSH keys' permissions.")
        files.add(rows.button_row("Copy my files now", "Plug in the drive first", "Copy", lambda: terminal(lennox_bin("lennox-safety"), "files"),
                                  "drive-removable-media-symbolic", suggested=True))
        files.add(rows.button_row("Restore my files", "From the drive back to this laptop", "Restore…",
                                  lambda: terminal(lennox_bin("lennox-safety"), "restore"), "document-revert-symbolic"))
        files.add(rows.entry_row(store, "safety.folders", "Folders to copy (comma separated, inside your home folder)"))
        files.add(rows.entry_row(store, "safety.drive", "Drive folder (empty = the roomiest drive found)"))
        files.add(rows.spin_row(store, "safety.remind_days", "Remind me after", "Days without a copy", lower=1, upper=365))
        page.add(files)

        heal = Adw.PreferencesGroup(
            title="Self-heal",
            description="Finds a blocked network, a stuck package lock, a full disk, a stopped bar or notifications, and the NVIDIA "
                        "driver missing for a new kernel. Fixes what is safe to fix.")
        heal.add(rows.switch_row(store, "safety.heal", "Warn me about blocked sites and a full disk"))
        heal.add(rows.button_row("Check and fix", "Opens a window and asks for your password only if a fix needs it", "Fix",
                                 lambda: terminal(lennox_bin("lennox-heal"), "fix"), "tools-symbolic"))
        heal.add(rows.button_row("Check every site", "Netflix, games, chat, downloads, school: DNS and connection", "Check",
                                 lambda: terminal(lennox_bin("lennox-net"), "check"), "network-wired-symbolic"))
        page.add(heal)
        self.widget = page

    def refresh(self):
        run_async([lennox_bin("lennox-safety"), "status", "--json"], self._got)

    def _got(self, ok, out, _err):
        try:
            info = json.loads(out) if ok else {}
        except ValueError:
            info = {}
        if not info:
            return
        if not info.get("snapper"):
            text = "Not set up (needs btrfs + snapper)"
        else:
            text = f"{info.get('snapshots', 0)} · last: {info.get('last_snapshot') or 'none yet'}"
        self.rows["System restore points"].value_label.set_label(text)
        days = info.get("files_days")
        self.rows["Files copied to a drive"].value_label.set_label(
            "Never" if days is None else ("today" if days == 0 else f"{days} day(s) ago"))
        drives = info.get("drives") or []
        self.rows["Drives found"].value_label.set_label(", ".join(drives) if drives else "None plugged in")
