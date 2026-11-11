"""The window for `lennox-ask`: type a question, read the answer."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import achievements  # noqa: E402
from . import ask  # noqa: E402


class AskWindow(Adw.ApplicationWindow):
    def __init__(self, app, question=""):
        super().__init__(application=app, title="Ask Claude", default_width=560, default_height=420)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
        self.entry = Gtk.Entry(placeholder_text="Ask anything, then press Enter", hexpand=True)
        self.entry.connect("activate", self.send)
        box.append(self.entry)
        self.answer = Gtk.Label(label="", wrap=True, xalign=0, yalign=0, selectable=True, vexpand=True)
        scroll = Gtk.ScrolledWindow(child=self.answer, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        box.append(scroll)
        bar = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.spinner = Gtk.Spinner()
        copy = Gtk.Button(label="Copy answer")
        copy.connect("clicked", lambda _b: self.get_clipboard().set(self.answer.get_label()))
        bar.append(self.spinner)
        bar.append(copy)
        box.append(bar)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(Adw.HeaderBar())
        self.set_content(view)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, kv, *_a: self.close() if kv == 65307 else False)   # Esc
        self.add_controller(keys)
        self.entry.grab_focus()
        if question:
            self.entry.set_text(question)
            GLib.idle_add(self.send, self.entry)

    def send(self, entry):
        question = entry.get_text().strip()
        if not question:
            return False
        self.answer.set_label("Thinking…")
        self.spinner.start()

        def work():
            try:
                text = ask.answer(question)
                achievements.tick("ask")
            except RuntimeError as e:
                text = str(e)
            GLib.idle_add(self.show, text)
        threading.Thread(target=work, daemon=True).start()
        return False

    def show(self, text):
        self.spinner.stop()
        self.answer.set_label(text)
        return False


def run(question=""):
    Adw.init()
    app = Adw.Application(application_id="dev.lennox.Ask")
    app.connect("activate", lambda a: AskWindow(a, question).present())
    return app.run([])
