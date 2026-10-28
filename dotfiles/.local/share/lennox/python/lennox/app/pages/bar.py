"""Bar & Dock: style, visible modules, dock behaviour."""

from gi.repository import Adw

from .. import rows
from ..util import launch, lennox_bin

STYLES = [
    ("modern", "Modern: floating pills (ML4W Modern)"),
    ("glass", "Glass: frosted islands (ML4W Glass)"),
    ("minimal", "Minimal: one thin strip (ML4W Minimal)"),
]


class Page:
    def __init__(self, ctx):
        store = ctx.store
        page = Adw.PreferencesPage()

        bar = Adw.PreferencesGroup(title="Top bar", description="Shortcuts: SUPER + CTRL + T style, SUPER + CTRL + B hide, SUPER + SHIFT + B reload.")
        bar.add(rows.switch_row(store, "bar.enabled", "Show the bar"))
        bar.add(rows.combo_row(store, "bar.style", "Style", STYLES))
        bar.add(rows.switch_row(store, "bar.clock_24h", "24-hour clock"))
        page.add(bar)

        modules = Adw.PreferencesGroup(title="What the bar shows")
        modules.add(rows.switch_row(store, "bar.show_window_title", "Window title"))
        modules.add(rows.switch_row(store, "bar.show_hardware", "CPU, memory, disk and GPU drawer"))
        modules.add(rows.switch_row(store, "bar.show_tray", "Tray icons", "Wi-Fi, Bluetooth, Discord, USB drives…"))
        modules.add(rows.switch_row(store, "bar.show_updates", "Update count"))
        modules.add(rows.switch_row(store, "bar.show_media", "Now playing", "Song or video that is playing"))
        page.add(modules)

        dock = Adw.PreferencesGroup(title="Dock", description="Shortcut: SUPER + CTRL + D shows or hides it.")
        dock.add(rows.switch_row(store, "dock.enabled", "Show the dock"))
        dock.add(rows.switch_row(store, "dock.autohide", "Hide automatically",
                                 "Appears when the mouse touches the bottom edge"))
        dock.add(rows.spin_row(store, "dock.icon_size", "Icon size", lower=24, upper=64, step=4))
        page.add(dock)

        reset = Adw.PreferencesGroup()
        reset.add(rows.button_row("Bar looks wrong?", "Restart the bar and the dock", "Restart",
                                  lambda: (launch([lennox_bin("lennox-bar"), "reload"]),
                                           launch([lennox_bin("lennox-dock"), "reload"]),
                                           ctx.toast("Restarted")),
                                  "view-refresh-symbolic"))
        page.add(reset)
        self.widget = page
