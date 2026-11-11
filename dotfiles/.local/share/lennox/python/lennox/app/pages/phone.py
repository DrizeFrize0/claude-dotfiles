"""Phone link (KDE Connect): pair your phone, see its battery, send files, find it."""

import json

from gi.repository import Adw, GLib, Gtk

from .. import rows
from ..util import have, launch, lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.device_rows = []
        page = Adw.PreferencesPage()

        how = Adw.PreferencesGroup(
            title="Phone link",
            description="Install KDE Connect on your phone (Android: Play Store or F-Droid; iPhone: App "
                        "Store), open it, and stay on the same Wi-Fi as this PC. Your phone shows up "
                        "below: press Pair, then accept on the phone.")
        how.add(rows.info_row("What you get",
                              "Phone notifications on the desktop · battery · send files both ways · "
                              "shared clipboard · ring your phone to find it · use the phone as a "
                              "touchpad or remote"))
        page.add(how)

        self.devices = Adw.PreferencesGroup(title="Phones")
        self.spinner = Gtk.Spinner()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                             tooltip_text="Look again", css_classes=["flat"])
        refresh.connect("clicked", lambda _b: self.refresh())
        suffix = Gtk.Box(spacing=6)
        suffix.append(self.spinner)
        suffix.append(refresh)
        self.devices.set_header_suffix(suffix)
        page.add(self.devices)

        more = Adw.PreferencesGroup()
        more.add(rows.link_row("Open KDE Connect", "Every setting: what the phone may do, folders, commands",
                               lambda: launch(["kdeconnect-app"]), "phone-symbolic"))
        page.add(more)
        self.more = more
        self.widget = page

    def refresh(self):
        self.spinner.start()
        run_async([lennox_bin("lennox-phone"), "status"], self._got)

    def _clear(self):
        for row in self.device_rows:
            self.devices.remove(row)
        self.device_rows = []

    def _add(self, row):
        self.devices.add(row)
        self.device_rows.append(row)

    def _got(self, ok, out, err):
        self.spinner.stop()
        self._clear()
        try:
            info = json.loads(out) if ok else None
        except ValueError:
            info = None
        self.more.set_visible(have("kdeconnect-app"))
        if not isinstance(info, dict):
            self._add(Adw.ActionRow(title="Couldn't ask KDE Connect", subtitle=GLib.markup_escape_text(
                err.strip()[-200:] or "No answer")))
            return
        if not info.get("installed"):
            self._add(Adw.ActionRow(title="KDE Connect is not installed",
                                    subtitle="Run lennox upgrade (or sudo pacman -S kdeconnect)"))
            return
        devices = info.get("devices") or []
        if not devices:
            self._add(Adw.ActionRow(title="No phone found yet",
                                    subtitle="Open KDE Connect on the phone, on the same Wi-Fi"))
            return
        for d in devices:
            self._add(self._device_row(d))

    def _device_row(self, d):
        if d.get("paired") and d.get("reachable"):
            state = "Connected"
            if d.get("battery") is not None:
                state += f" · battery {d['battery']}%" + (" (charging)" if d.get("charging") else "")
        elif d.get("paired"):
            state = "Paired, not nearby (same Wi-Fi?)"
        else:
            state = "Not paired yet"
        row = Adw.ExpanderRow(title=GLib.markup_escape_text(d["name"]), subtitle=state)
        row.add_prefix(Gtk.Image.new_from_icon_name("phone-symbolic"))
        ident = d["id"]
        if not d.get("paired"):
            row.add_suffix(self._button("Pair", lambda: self._act("pair", ident, "Accept on your phone"),
                                        ["suggested-action"]))
            row.set_enable_expansion(False)
            return row
        if d.get("reachable"):
            row.add_row(rows.button_row("Find my phone", "Rings it, even on silent", "Ring",
                                        lambda: self._act("ring", ident, "Ringing your phone"),
                                        "audio-volume-high-symbolic"))
            row.add_row(rows.button_row("Send files", None, "Choose…", lambda: self._send(ident),
                                        "document-send-symbolic"))
            row.add_row(rows.button_row("Send what I copied", "Text or a link, to the phone's clipboard",
                                        "Send", lambda: self._act("clipboard", ident, "Sent to your phone"),
                                        "edit-paste-symbolic"))
            row.add_row(rows.button_row("Ping", "Check the link works", "Ping",
                                        lambda: self._act("ping", ident, "Pinged"), "network-transmit-symbolic"))
        row.add_row(rows.button_row("Unpair", "Forget this phone", "Unpair",
                                    lambda: self._act("unpair", ident, "Unpaired"), "edit-delete-symbolic"))
        return row

    def _button(self, label, callback, classes):
        button = Gtk.Button(label=label, valign=Gtk.Align.CENTER, css_classes=classes)
        button.connect("clicked", lambda _b: callback())
        return button

    def _act(self, action, ident, done_text, *extra):
        def done(ok, _out, err):
            self.ctx.toast(done_text if ok else (err.strip().splitlines() or ["It didn't work"])[-1])
            if action in ("pair", "unpair"):
                GLib.timeout_add_seconds(3, lambda: (self.refresh(), False)[1])
        run_async([lennox_bin("lennox-phone"), action, ident, *extra], done)

    def _send(self, ident):
        dialog = Gtk.FileDialog(title="Send to your phone")

        def chosen(dlg, result):
            try:
                files = dlg.open_multiple_finish(result)
            except GLib.Error:
                return                                   # cancelled
            paths = [files.get_item(i).get_path() for i in range(files.get_n_items())]
            paths = [p for p in paths if p]
            if paths:
                self._act("send", ident, f"Sending {len(paths)} file{'s' * (len(paths) != 1)}…", *paths)

        dialog.open_multiple(self.ctx.window, None, chosen)
