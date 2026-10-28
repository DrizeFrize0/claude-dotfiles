"""Small helpers: running commands without blocking the window, paths."""

import os
import shutil

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GLib  # noqa: E402

HOME = os.path.expanduser("~")
BIN = os.path.join(HOME, ".local", "bin")
ASSETS = os.path.join(HOME, ".config", "lennox", "assets")


def lennox_bin(name):
    """Absolute path of a lennox-* command."""
    return os.path.join(BIN, name)


def have(program):
    return shutil.which(program) is not None


def run_async(argv, on_done=None):
    """Run a command in the background; call on_done(ok, stdout, stderr) when it ends."""
    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
    try:
        proc = Gio.Subprocess.new(argv, flags)
    except GLib.Error as e:
        if on_done:
            on_done(False, "", e.message)
        return

    def finished(p, result):
        try:
            _, out, err = p.communicate_utf8_finish(result)
            ok = p.get_successful()
        except GLib.Error as e:
            ok, out, err = False, "", e.message
        if on_done:
            on_done(ok, out or "", err or "")

    proc.communicate_utf8_async(None, None, finished)


def launch(argv):
    """Start a separate program (an app or a terminal) that outlives the window."""
    try:
        Gio.Subprocess.new(["setsid", "-f", *argv], Gio.SubprocessFlags.NONE)
        return True
    except GLib.Error:
        return False


def read_file(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


class Debouncer:
    """Call `func` once, `delay_ms` after the last trigger (for sliders)."""

    def __init__(self, delay_ms, func):
        self.delay_ms = delay_ms
        self.func = func
        self.source = 0
        self.args = ()

    def trigger(self, *args):
        self.args = args
        if self.source:
            GLib.source_remove(self.source)
        self.source = GLib.timeout_add(self.delay_ms, self._fire)

    def _fire(self):
        self.source = 0
        self.func(*self.args)
        return GLib.SOURCE_REMOVE
