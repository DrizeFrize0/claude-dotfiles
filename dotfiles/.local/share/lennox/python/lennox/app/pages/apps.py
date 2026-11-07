"""Default apps opened by the shortcuts and the bar."""

import shlex
import shutil

from gi.repository import Adw

from .. import rows

APPS = [
    ("apps.terminal", "Terminal (SUPER + RETURN)", "kitty"),
    ("apps.browser", "Browser (SUPER + B)", "flatpak run app.zen_browser.zen"),
    ("apps.filemanager", "Files (SUPER + E)", "nautilus"),
    ("apps.editor", "Code editor", "code"),
    ("apps.calculator", "Calculator (SUPER + C)", "gnome-calculator"),
    ("apps.system_monitor", "System monitor", "missioncenter"),
    ("apps.audio_mixer", "Audio mixer", "pavucontrol"),
]


def _check(text):
    try:
        program = shlex.split(text)[0]
    except (ValueError, IndexError):
        return "Type a command, e.g. firefox"
    if not shutil.which(program):
        return f"'{program}' is not installed"
    return None


class Page:
    def __init__(self, ctx):
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Default apps",
            description="Type the command that starts the app, then press ✓. "
                        "Examples: firefox · flatpak run app.zen_browser.zen · thunar · alacritty")
        for path, title, _default in APPS:
            group.add(rows.entry_row(ctx.store, path, title, _check,
                                     lambda ok, text: ctx.toast("Saved" if ok else text)))
        page.add(group)
        self.widget = page
