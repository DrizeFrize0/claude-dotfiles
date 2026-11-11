"""Passwords: Bitwarden on the laptop, in Zen and on the phone, plus importing."""

import json
import os
import re

from gi.repository import Adw, Gtk

from .. import rows
from ..util import have, launch, lennox_bin, run_async

SIGN_UP = {"us": "https://vault.bitwarden.com/#/register", "eu": "https://vault.bitwarden.eu/#/register"}
IMPORT = {"us": "https://vault.bitwarden.com/#/tools/import", "eu": "https://vault.bitwarden.eu/#/tools/import"}
ZEN_ADDON = "https://addons.mozilla.org/firefox/addon/bitwarden-password-manager/"
GOOGLE_EXPORT = "https://passwords.google.com/options?ep=1"
PHONE_APP = "https://bitwarden.com/download/#downloads-mobile"
IMPORT_HELP = "https://bitwarden.com/help/import-data/"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _open(url):
    launch(["xdg-open", url])


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.region = "us"
        page = Adw.PreferencesPage()

        intro = Adw.PreferencesGroup(
            title="Your passwords, everywhere",
            description="Lennox uses Bitwarden: free, open source and end-to-end encrypted, so only your master "
                        "password can open the vault (not even Bitwarden can read it). The same vault fills "
                        "passwords on this laptop, in Zen and on your phone.")
        self.status_row = rows.info_row("Status", "checking…")
        self.status_row.add_prefix(Gtk.Image.new_from_icon_name("dialog-password-symbolic"))
        intro.add(self.status_row)
        self.lock_row = rows.button_row("Lock the vault now", "It also locks by itself after 15 minutes and "
                                        "whenever the screen locks", "Lock", self._lock, "changes-prevent-symbolic")
        intro.add(self.lock_row)
        page.add(intro)

        # 1. Account + this laptop
        account = Adw.PreferencesGroup(
            title="1. Connect your account",
            description="No account yet? Make a free one first. Pick a master password you will never forget: "
                        "nobody can reset it for you.")
        account.add(rows.link_row("Create a free Bitwarden account", "Opens bitwarden.com",
                                  lambda: _open(SIGN_UP[self.region]), "list-add-symbolic"))
        self.email_row = Adw.EntryRow(title="Bitwarden email")
        self.email_row.set_input_purpose(Gtk.InputPurpose.EMAIL)
        account.add(self.email_row)
        self.region_row = Adw.ComboRow(title="Server", subtitle="Where you made the account")
        self.region_row.set_model(Gtk.StringList.new(["bitwarden.com (US)", "bitwarden.eu (Europe)"]))
        self.region_row.connect("notify::selected", self._on_region)
        account.add(self.region_row)
        account.add(rows.button_row("Connect this laptop",
                                    "Opens a small window: paste your API key once, then your master password",
                                    "Connect", self._connect, "network-transmit-receive-symbolic", suggested=True))
        page.add(account)

        # 2. Browser + app
        browser = Adw.PreferencesGroup(
            title="2. Fill in Zen and apps",
            description="SUPER + P fills a login in any app (pick it, Lennox types the username and password). "
                        "In Zen the Bitwarden add-on fills and saves logins on websites.")
        browser.add(rows.link_row("Add Bitwarden to Zen", "Then sign in to the add-on with the same account",
                                  lambda: _open(ZEN_ADDON), "web-browser-symbolic"))
        browser.add(rows.info_row("Tip", "In Zen, turn off Settings > Privacy > \"Ask to save passwords\" so "
                                         "only Bitwarden saves them"))
        if have("bitwarden-desktop"):
            browser.add(rows.link_row("Open the Bitwarden app", "Browse, edit and generate passwords",
                                      lambda: launch(["bitwarden-desktop"]), "dialog-password-symbolic"))
        page.add(browser)

        # 3. Import
        imports = Adw.PreferencesGroup(
            title="3. Bring your passwords in",
            description="Export from the old place, then import the file into Bitwarden. "
                        "The import page is in your Bitwarden vault: choose the format, pick the file, done.")

        google = Adw.ExpanderRow(title="From Google / Chrome", subtitle="Saved in Chrome or your Google account")
        google.add_prefix(Gtk.Image.new_from_icon_name("web-browser-symbolic"))
        google.add_row(self._step("1", "Download your passwords from Google",
                                  "Sign in, choose Export passwords (it saves a .csv to Downloads)",
                                  "Open", lambda: _open(GOOGLE_EXPORT)))
        google.add_row(self._step("2", "Import into Bitwarden",
                                  "File format: Chrome (csv), then pick the file from Downloads",
                                  "Open", lambda: _open(IMPORT[self.region])))
        imports.add(google)

        phone = Adw.ExpanderRow(title="From your phone", subtitle="iPhone (iCloud Keychain) or Samsung Pass")
        phone.add_prefix(Gtk.Image.new_from_icon_name("phone-symbolic"))
        phone.add_row(self._step("1", "Install Bitwarden on the phone",
                                 "Sign in with the same account; it syncs with this laptop",
                                 "Get", lambda: _open(PHONE_APP)))
        phone.add_row(rows.info_row("iPhone",
                                    "Passwords app > ••• > Export Data to Another App > Bitwarden (newer iOS); "
                                    "on older iOS export from a Mac, or use the guide"))
        phone.add_row(rows.info_row("Samsung / Android",
                                    "Most Android passwords are in Google: use the Google steps. "
                                    "Samsung Pass can't export to a file, so move those by hand or via the guide"))
        phone.add_row(self._step("2", "Step-by-step guide", "Bitwarden's import help for every app",
                                 "Open", lambda: _open(IMPORT_HELP)))
        imports.add(phone)

        other = Adw.ExpanderRow(title="From another password manager",
                                subtitle="LastPass, 1Password, Dashlane, NordPass, Proton Pass, Firefox, Edge…")
        other.add_prefix(Gtk.Image.new_from_icon_name("document-open-symbolic"))
        other.add_row(self._step("1", "Export from the old manager",
                                 "Look for Export in its settings (the guide shows where for each one)",
                                 "Guide", lambda: _open(IMPORT_HELP)))
        other.add_row(self._step("2", "Import into Bitwarden", "Choose the matching file format, then pick the file",
                                 "Open", lambda: _open(IMPORT[self.region])))
        imports.add(other)
        page.add(imports)

        # 4. Clean up
        clean = Adw.PreferencesGroup(
            title="4. Delete the exported file",
            description="An exported file holds every password in plain text. Once the import worked, "
                        "wipe it so nobody can read it later.")
        self.exports_row = Adw.ActionRow(title="Exported password files in Downloads", subtitle="checking…")
        self.exports_row.add_prefix(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        self.clean_button = Gtk.Button(label="Delete safely", valign=Gtk.Align.CENTER)
        self.clean_button.add_css_class("destructive-action")
        self.clean_button.connect("clicked", lambda _b: self._confirm_clean())
        self.exports_row.add_suffix(self.clean_button)
        clean.add(self.exports_row)
        page.add(clean)

        keys = Adw.PreferencesGroup(title="Shortcuts in the SUPER + P list")
        for combo, what in (("Enter", "Type the username, Tab, then the password"),
                            ("Alt + 2", "Type only the username"), ("Alt + 3", "Type only the password"),
                            ("Alt + 4", "Type the 2FA code"),
                            ("Alt + C", "Copy the password (clears in 20 s, never saved in clipboard history)"),
                            ("Alt + T", "Copy the 2FA code"), ("Alt + S", "Sync with your phone and Zen now")):
            keys.add(rows.info_row(combo, what))
        page.add(keys)

        self.widget = page

    @staticmethod
    def _step(number, title, subtitle, label, callback):
        row = rows.button_row(title, subtitle, label, callback)
        badge = Gtk.Label(label=number, valign=Gtk.Align.CENTER, width_chars=2)
        badge.add_css_class("dim-label")
        row.add_prefix(badge)
        return row

    # ---------------------------------------------------------------- state

    def refresh(self):
        def got_status(ok, out, _err):
            try:
                status = json.loads(out) if ok else {}
            except ValueError:
                status = {}
            if not status.get("installed"):
                self.status_row.value_label.set_label("Not installed yet (run: lennox upgrade)")
                self.lock_row.set_visible(False)
                return
            email = status.get("email") or ""
            self.region = "eu" if status.get("region") == "eu" else "us"
            self.region_row.set_selected(1 if self.region == "eu" else 0)
            if email and not self.email_row.get_text():
                self.email_row.set_text(email)
            if not email:
                text = "Not connected yet: start with step 1"
            elif status.get("unlocked"):
                text = f"Unlocked · {email}"
            else:
                text = f"Locked · {email} (SUPER + P unlocks it)"
            self.status_row.value_label.set_label(text)
            self.lock_row.set_visible(bool(status.get("unlocked")))

        run_async([lennox_bin("lennox-passwords"), "status"], got_status)
        self._check_exports()

    def _check_exports(self):
        def got(ok, out, _err):
            files = [line for line in out.splitlines() if line.strip()] if ok else []
            self.exports = files
            if files:
                names = ", ".join(os.path.basename(f) for f in files[:3])
                more = f" and {len(files) - 3} more" if len(files) > 3 else ""
                self.exports_row.set_subtitle(f"Found: {names}{more}")
            else:
                self.exports_row.set_subtitle("None found. Nothing to clean up")
            self.clean_button.set_sensitive(bool(files))

        self.exports = []
        run_async([lennox_bin("lennox-passwords"), "exports"], got)

    def _on_region(self, row, _param):
        self.region = "eu" if row.get_selected() == 1 else "us"

    # ---------------------------------------------------------------- actions

    def _connect(self):
        email = self.email_row.get_text().strip()
        if not EMAIL.match(email):
            self.email_row.add_css_class("error")
            self.ctx.toast("Type your Bitwarden email first")
            return
        self.email_row.remove_css_class("error")
        if not have("rbw"):
            self.ctx.toast("Passwords aren't installed yet. Run: lennox upgrade")
            return

        def done(ok, _out, err):
            if ok:
                self.ctx.toast("Follow the steps in the new window")
            else:
                self.ctx.toast(f"Could not connect: {err.strip() or 'unknown error'}", 5)
            self.refresh()

        run_async([lennox_bin("lennox-passwords"), "setup", email, self.region], done)

    def _lock(self):
        run_async([lennox_bin("lennox-passwords"), "lock"], lambda *_: (self.ctx.toast("Vault locked"), self.refresh()))

    def _confirm_clean(self):
        count = len(self.exports)
        dialog = Adw.AlertDialog(
            heading="Delete exported passwords?",
            body=f"{count} file{'s' if count != 1 else ''} in Downloads will be overwritten and deleted. "
                 "Check your passwords are in Bitwarden first; this can't be undone.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def chosen(_d, response):
            if response != "delete":
                return

            def done(ok, _out, _err):
                self.ctx.toast("Exported passwords deleted" if ok else "Some files could not be deleted")
                self._check_exports()

            run_async([lennox_bin("lennox-passwords"), "clean-exports"], done)

        dialog.connect("response", chosen)
        dialog.present(self.ctx.window)
