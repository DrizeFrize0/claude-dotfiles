"""Clipboard history: search what you copied, copy it again, pin the useful bits."""

from gi.repository import Adw, GLib, Gtk

from ... import clipboard as C
from ..util import have, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.items = []
        self.history_rows = []
        self.pin_rows = []
        self.pins = C.load_pins()
        page = Adw.PreferencesPage()

        top = Adw.PreferencesGroup(
            title="Clipboard",
            description="Everything you copied lately (SUPER + V shows it anywhere). Click a row to copy it "
                        "again. Pin things you paste often: pins stay after the history is cleared.")
        self.search = Gtk.SearchEntry(placeholder_text="Search what you copied", hexpand=True)
        self.search.connect("search-changed", lambda _e: self._show_history())
        top.add(self.search)
        page.add(top)

        self.pin_group = Adw.PreferencesGroup(title="Pinned")
        page.add(self.pin_group)
        self.history = Adw.PreferencesGroup(title="History")
        self.clear_button = Gtk.Button(label="Clear history", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
        self.clear_button.connect("clicked", lambda _b: self._confirm_clear())
        self.history.set_header_suffix(self.clear_button)
        page.add(self.history)
        self.widget = page

    def refresh(self):
        self.pins = C.load_pins()
        self._show_pins()
        if not have("cliphist"):
            self._set_history_rows([self._note("Clipboard history needs cliphist", "Run: lennox upgrade")])
            return
        run_async(["cliphist", "list"], self._got_list)

    def _note(self, title, subtitle=None):
        return Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=subtitle or "")

    # ------------------------------------------------------------ pins

    def _clear_rows(self, group, rows):
        for row in rows:
            group.remove(row)
        rows.clear()

    def _show_pins(self):
        self._clear_rows(self.pin_group, self.pin_rows)
        self.pin_group.set_visible(bool(self.pins))
        for text in self.pins:
            row = Adw.ActionRow(title=GLib.markup_escape_text(C.one_line(text)), activatable=True, title_lines=1)
            row.connect("activated", lambda _r, t=text: self._copy_text(t))
            row.add_suffix(self._icon_button("window-close-symbolic", "Unpin", lambda t=text: self._unpin(t)))
            row.add_prefix(Gtk.Image.new_from_icon_name("view-pin-symbolic"))
            self.pin_group.add(row)
            self.pin_rows.append(row)

    def _unpin(self, text):
        self.pins = [p for p in self.pins if p != text]
        C.save_pins(self.pins)
        self._show_pins()

    def _pin(self, item):
        def got(ok, out, _err):
            if not ok or not out.strip():
                self.ctx.toast("Couldn't pin that")
                return
            self.pins = C.add_pin(self.pins, out)
            C.save_pins(self.pins)
            self._show_pins()
            self.ctx.toast("Pinned")

        run_async(["cliphist", "decode", item["id"]], got)

    # ------------------------------------------------------------ history

    def _got_list(self, ok, out, _err):
        self.items = C.parse_list(out) if ok else []
        self._show_history()

    def _set_history_rows(self, rows):
        self._clear_rows(self.history, self.history_rows)
        for row in rows:
            self.history.add(row)
            self.history_rows.append(row)

    def _show_history(self):
        found = C.search(self.items, self.search.get_text())
        self.clear_button.set_sensitive(bool(self.items))
        if not found:
            self._set_history_rows([self._note("Nothing found" if self.items else "Nothing copied yet")])
            return
        rows = []
        for item in found:
            title = "Image" if item["image"] else C.one_line(item["text"])
            row = Adw.ActionRow(title=GLib.markup_escape_text(title or "(empty)"), activatable=True, title_lines=1)
            row.connect("activated", lambda _r, i=item: self._copy_item(i))
            if item["image"]:
                row.add_prefix(Gtk.Image.new_from_icon_name("image-x-generic-symbolic"))
            else:
                row.add_suffix(self._icon_button("view-pin-symbolic", "Pin", lambda i=item: self._pin(i)))
            row.add_suffix(self._icon_button("user-trash-symbolic", "Remove", lambda i=item: self._delete(i)))
            rows.append(row)
        self._set_history_rows(rows)

    def _icon_button(self, icon, tip, callback):
        button = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER, tooltip_text=tip, css_classes=["flat"])
        button.connect("clicked", lambda _b: callback())
        return button

    def _copy_item(self, item):
        run_async(["sh", "-c", 'cliphist decode "$1" | wl-copy', "sh", item["id"]],
                  lambda ok, _o, _e: self.ctx.toast("Copied" if ok else "Couldn't copy that"))

    def _copy_text(self, text):
        run_async(["sh", "-c", 'printf "%s" "$1" | wl-copy', "sh", text],
                  lambda ok, _o, _e: self.ctx.toast("Copied" if ok else "Couldn't copy that"))

    def _delete(self, item):
        run_async(["sh", "-c", 'printf "%s\\n" "$1" | cliphist delete', "sh", item["line"]],
                  lambda *_a: self.refresh())

    def _confirm_clear(self):
        dialog = Adw.AlertDialog(heading="Clear the clipboard history?",
                                 body="Everything you copied is forgotten. Pinned items stay.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def chosen(_d, response):
            if response == "clear":
                run_async(["cliphist", "wipe"], lambda *_a: self.refresh())

        dialog.connect("response", chosen)
        dialog.present(self.ctx.window)
