"""Graphics: Intel + NVIDIA (GTX 1650) hybrid setup, game mode."""

from gi.repository import Adw

from .. import rows
from ..util import have, launch, lennox_bin, run_async

MODES = [
    ("auto", "Automatic (recommended)"),
    ("integrated", "Intel only: longest battery"),
    ("hybrid", "Intel + NVIDIA: external screens on NVIDIA ports"),
]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        store = ctx.store
        page = Adw.PreferencesPage()

        self.status_group = Adw.PreferencesGroup(title="Status")
        self.status_rows = {}
        for key in ("NVIDIA GPU", "Power state", "Driver", "Kernel modeset", "Desktop runs on"):
            row = rows.info_row(key, "…")
            self.status_rows[key] = row
            self.status_group.add(row)
        page.add(self.status_group)

        mode = Adw.PreferencesGroup(
            title="Which GPU runs the desktop",
            description="The desktop runs on Intel so the GTX 1650 can sleep. Games still use the GTX: Steam/Proton picks "
                        "it on its own, Minecraft (Prism Launcher) is set up for it, and anything else runs on it with "
                        "`prime-run app` or `lennox gpu run app`. Changes apply at the next login.")
        mode.add(rows.combo_row(store, "gpu.mode", "Mode", MODES))
        page.add(mode)

        gaming = Adw.PreferencesGroup(title="Gaming")
        self.game_row = Adw.SwitchRow(title="Game mode",
                                      subtitle="No effects, performance power mode, notifications paused (SUPER + ALT + G)")
        self.game_row.connect("notify::active", self._on_game)
        gaming.add(self.game_row)
        gaming.add(rows.info_row("Steam games that use OpenGL", "Launch options: prime-run %command%"))
        if have("nvidia-settings"):
            gaming.add(rows.link_row("NVIDIA Settings", "Driver details, temperature, clocks",
                                     lambda: launch(["nvidia-settings"]), "applications-games-symbolic"))
        page.add(gaming)
        self.widget = page

    def refresh(self):
        def got_status(ok, out, _err):
            found = False
            for line in out.splitlines():
                key, _, value = line.partition(":")
                key, value = key.strip(), value.strip()
                if key in self.status_rows:
                    found = True
                    self.status_rows[key].value_label.set_label(value)
            if not found:
                self.status_group.set_description(out.strip() or "No NVIDIA GPU found.")
                for row in self.status_rows.values():
                    row.set_visible(False)

        run_async([lennox_bin("lennox-gpu"), "status"], got_status)

        def got_game(_ok, out, _err):
            self.updating = True
            self.game_row.set_active(out.strip() == "on")
            self.updating = False

        run_async([lennox_bin("lennox-mode"), "game", "status"], got_game)

    def _on_game(self, row, _param):
        if not self.updating:
            run_async([lennox_bin("lennox-mode"), "game", "on" if row.get_active() else "off"])
