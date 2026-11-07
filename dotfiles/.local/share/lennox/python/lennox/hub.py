"""Jado's hub as an app: its web page in its own window, no browser around it.

    python3 -m lennox.hub URL

Uses WebKitGTK (package webkitgtk-6.0). Exits with 3 when that isn't installed,
so lennox-hub can open the page another way.
"""

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit
except (ValueError, ImportError):
    WebKit = None
from gi.repository import Gio, GLib, Gtk  # noqa: E402


def main(argv):
    if WebKit is None:
        return 3
    url = argv[1] if len(argv) > 1 else ""
    if not url:
        return 2
    GLib.set_prgname("lennox-hub")
    data = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "lennox", "hub-web")
    session = WebKit.NetworkSession.new(data, os.path.join(data, "cache"))

    def activate(app):
        win = Gtk.ApplicationWindow(application=app, title="Jado's hub", default_width=1100, default_height=720)
        view = WebKit.WebView(network_session=session)
        view.load_uri(url)
        win.set_child(view)
        win.present()

    app = Gtk.Application(application_id="lennox.hub", flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", activate)
    return app.run([argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
