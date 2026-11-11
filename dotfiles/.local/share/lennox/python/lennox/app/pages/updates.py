"""Updates: automatic system/driver updates, AUR apps, Lennox itself."""

import json

from gi.repository import Adw, Gtk

from .. import rows
from ..util import have, launch, lennox_bin, read_file, run_async

CONF = "/etc/lennox/autoupdate.conf"
STATUS = "/var/lib/lennox/autoupdate-status.json"


def _conf_enabled():
    for line in read_file(CONF).splitlines():
        if line.startswith("ENABLED="):
            return line.split("=", 1)[1].strip().strip('"') == "true"
    return False


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        page = Adw.PreferencesPage()

        auto = Adw.PreferencesGroup(
            title="Automatic updates",
            description="The system, kernel and every driver (NVIDIA, sound and mic firmware, touchpad, Wi-Fi) "
                        "update by themselves about once a day, only on the charger and never on a phone hotspot. "
                        "On btrfs a snapshot is taken first, and Lennox pauses when Arch news says an update needs you.")
        self.auto_row = Adw.SwitchRow(title="Install updates automatically")
        self.auto_row.connect("notify::active", self._on_auto)
        auto.add(self.auto_row)
        self.last_row = rows.info_row("Last run", "…")
        auto.add(self.last_row)
        self.reboot_banner = Adw.ActionRow(title="Restart to finish", subtitle="A new kernel or driver is waiting")
        self.reboot_banner.add_prefix(Gtk.Image.new_from_icon_name("system-reboot-symbolic"))
        restart = Gtk.Button(label="Restart", valign=Gtk.Align.CENTER)
        restart.add_css_class("suggested-action")
        restart.connect("clicked", lambda _b: launch([lennox_bin("lennox-power"), "reboot"]))
        self.reboot_banner.add_suffix(restart)
        auto.add(self.reboot_banner)
        page.add(auto)

        self.news_group = Adw.PreferencesGroup(title="Paused for Arch news",
                                               description="Read this first; it explains a one-time manual step.")
        page.add(self.news_group)
        self.news_rows = []

        now = Adw.PreferencesGroup(title="Update now")
        self.count_row = rows.info_row("Waiting", "checking…")
        now.add(self.count_row)
        now.add(rows.button_row("Everything", "System, drivers, AUR apps and Flatpaks, in a terminal window",
                                "Update", lambda: launch([lennox_bin("lennox-update")]),
                                "software-update-available-symbolic", suggested=True))
        now.add(rows.button_row("Lennox itself", "New Lennox features and fixes from its git repository",
                                "Update", self._update_lennox, "view-refresh-symbolic"))
        if have("fwupdmgr"):
            now.add(rows.button_row("Firmware (BIOS, touchpad, SSD)", "Checks your laptop maker's firmware updates",
                                    "Check", self._firmware, "drive-harddisk-symbolic"))
        page.add(now)

        if have("btrfs-assistant-launcher") or have("btrfs-assistant"):
            snaps = Adw.PreferencesGroup(title="Snapshots",
                                         description="A restore point is made before and after every update. If an update "
                                                     "ever breaks something, pick an older snapshot in the boot menu.")
            snaps.add(rows.link_row("Manage snapshots", "Btrfs Assistant",
                                    lambda: launch(["btrfs-assistant-launcher" if have("btrfs-assistant-launcher")
                                                    else "btrfs-assistant"]), "document-revert-symbolic"))
            page.add(snaps)

        self.widget = page

    def refresh(self):
        self.updating = True
        self.auto_row.set_active(_conf_enabled())
        self.updating = False

        try:
            status = json.loads(read_file(STATUS, "{}"))
        except ValueError:
            status = {}
        if status:
            self.last_row.value_label.set_label(f"{status.get('time', '?')} · {status.get('message', '')}")
        else:
            self.last_row.value_label.set_label("Not yet (the first check runs 10 minutes after boot)")
        self.reboot_banner.set_visible(bool(status.get("reboot_needed")))

        for row in self.news_rows:
            self.news_group.remove(row)
        self.news_rows = []
        news = status.get("held_news") or []
        self.news_group.set_visible(bool(news) and status.get("result") == "held")
        for item in news:
            row = Adw.ActionRow(title=item.get("title", "Arch news"), use_markup=False)
            read = Gtk.Button(label="Read", valign=Gtk.Align.CENTER)
            read.connect("clicked", lambda _b, link=item.get("link", "https://archlinux.org/news/"): launch(["xdg-open", link]))
            row.add_suffix(read)
            self.news_group.add(row)
            self.news_rows.append(row)
        if news:
            ack = rows.button_row("Done reading?", "Continue the automatic updates", "Continue", self._ack_news,
                                  "emblem-ok-symbolic", suggested=True)
            self.news_group.add(ack)
            self.news_rows.append(ack)

        def got_count(ok, out, _err):
            try:
                repo, aur = (int(x) for x in out.split())
            except ValueError:
                self.count_row.value_label.set_label("could not check (offline?)")
                return
            self.count_row.value_label.set_label(
                f"{repo} system (auto) · {aur} AUR app{'s' if aur != 1 else ''} (one click)" if repo or aur else "Up to date")

        run_async([lennox_bin("lennox-updates"), "count"], got_count)

    def _on_auto(self, row, _param):
        if self.updating:
            return
        flag = "--enable" if row.get_active() else "--disable"

        def done(ok, _out, err):
            if ok:
                self.ctx.toast("Automatic updates on" if flag == "--enable" else "Automatic updates off")
            else:
                self.ctx.toast("Not changed (password needed)" if "dismissed" in err.lower() or not err.strip()
                               else f"Not changed: {err.strip()[-100:]}", 5)
            self.refresh()

        run_async(["pkexec", "/usr/local/bin/lennox-autoupdate", flag], done)

    def _ack_news(self):
        def done(ok, _out, _err):
            self.ctx.toast("Updating now in the background" if ok else "Not changed (password needed)")
            self.refresh()

        run_async(["pkexec", "/usr/local/bin/lennox-autoupdate", "--ack-news"], done)

    def _update_lennox(self):
        launch(["kitty", "--class", "lennox-floating", "--title", "Update Lennox", "--hold",
                lennox_bin("lennox-update-dotfiles")])

    def _firmware(self):
        launch(["kitty", "--class", "lennox-floating", "--title", "Firmware updates", "--hold", "bash", "-c",
                "fwupdmgr refresh --force; fwupdmgr get-updates && fwupdmgr update"])
