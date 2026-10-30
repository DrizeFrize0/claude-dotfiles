"""Game center: clips, performance, launchers, the FPS overlay and your Minecraft server."""

import json
import os

from gi.repository import Adw, Gdk, Gtk

from .. import rows
from ..util import have, launch, lennox_bin, run_async

CLIP_MODES = [("gaming", "While gaming"), ("always", "Always"), ("off", "Off")]
STEAM_OPTION = "lennox-gpu run mangohud %command%"
LAUNCHERS = [("steam", "Steam", "Your library (games run on the GTX 1650 with the launch option below)", "steam"),
             ("prismlauncher", "Minecraft", "Prism Launcher", "org.prismlauncher.PrismLauncher"),
             ("lutris", "Lutris", "Other stores and emulators", "lutris"),
             ("heroic", "Heroic", "Epic, GOG and Amazon games", "heroic")]
PERF_MODES = [("quiet", "Quiet: cooler, quieter, longest battery"), ("balanced", "Balanced"),
              ("max", "Max performance")]


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        store = ctx.store
        page = Adw.PreferencesPage()

        play = Adw.PreferencesGroup(title="Play")
        found = False
        for command, title, subtitle, icon in LAUNCHERS:
            if have(command):
                found = True
                play.add(rows.link_row(title, subtitle, lambda c=command: launch([c]), icon))
        play.add(rows.button_row("Game mode", "Max performance, effects off, no notifications (SUPER + ALT + G)",
                                 "Toggle", lambda: run_async([lennox_bin("lennox-mode"), "game", "toggle"]),
                                 "input-gaming-symbolic"))
        if not found:
            play.set_description("Install Steam and Prism Launcher by running the Lennox installer with gaming on.")
        page.add(play)

        clips = Adw.PreferencesGroup(
            title="Clips",
            description="Like ShadowPlay: the last minutes of gameplay are kept ready, and SUPER + ALT + R "
                        "saves them. A notification offers a vertical 9:16 copy for TikTok, Shorts and Reels. "
                        "Uses the graphics chip's video encoder, so games don't slow down.")
        clips.add(rows.combo_row(store, "clips.mode", "Record", CLIP_MODES))
        clips.add(rows.spin_row(store, "clips.seconds", "Clip length", "Seconds saved by SUPER + ALT + R",
                                lower=10, upper=600, step=10))
        clips.add(rows.switch_row(store, "clips.mic", "Include my microphone"))
        clips.add(rows.entry_row(store, "clips.folder", "Folder"))
        self.clip_status = rows.info_row("Recorder", "…")
        clips.add(self.clip_status)
        clips.add(rows.link_row("Open the clips folder", None, self._open_clips, "folder-videos-symbolic"))
        page.add(clips)

        perf = Adw.PreferencesGroup(
            title="Performance",
            description="Also in the bar and on SUPER + ALT + P. Game mode switches to Max by itself.")
        self.perf_row = Adw.ComboRow(title="Mode")
        self.perf_row.set_model(Gtk.StringList.new([label for _, label in PERF_MODES]))
        self.perf_row.connect("notify::selected", self._on_perf)
        perf.add(self.perf_row)
        page.add(perf)

        overlay = Adw.PreferencesGroup(
            title="FPS overlay",
            description="FPS, frame times, CPU / GPU load and temperatures, RAM. Shift + F12 shows or hides it "
                        "in any game it's on. Steam: right-click a game > Properties > Launch options. "
                        "Prism Launcher: Settings > Minecraft > Tweaks > Enable MangoHud.")
        overlay.add(rows.combo_row(store, "games.overlay", "When a game starts",
                                   [("hidden", "Hidden (Shift + F12 shows it)"), ("shown", "Shown")]))
        overlay.add(rows.button_row("Steam launch option", STEAM_OPTION + "  (GTX 1650 + overlay)", "Copy",
                                    self._copy_option, "edit-copy-symbolic"))
        page.add(overlay)

        server = Adw.PreferencesGroup(
            title="Minecraft server",
            description="Players online in the bar (click it to open Prism Launcher), and a notification "
                        "when someone joins.")
        server.add(rows.entry_row(store, "games.mc_server", "Server address (empty = off)"))
        server.add(rows.switch_row(store, "games.mc_joins", "Tell me when someone joins"))
        self.server_row = rows.info_row("Right now", "checking…")
        server.add(self.server_row)
        page.add(server)
        self.page = page
        self.widget = page

    def refresh(self):
        run_async([lennox_bin("lennox-clips"), "status"],
                  lambda ok, out, _e: self.clip_status.value_label.set_label(
                      "Recording now (SUPER + ALT + R saves)" if out.strip() == "on"
                      else ("Not installed: run lennox upgrade" if not have("gpu-screen-recorder")
                            else "Waiting for a game")))

        def got_perf(ok, out, _err):
            values = [v for v, _ in PERF_MODES]
            self.updating = True
            self.perf_row.set_sensitive(ok and out.strip() in values)
            if out.strip() in values:
                self.perf_row.set_selected(values.index(out.strip()))
            else:
                self.perf_row.set_subtitle("Not available on this laptop (power-profiles-daemon)")
            self.updating = False

        run_async([lennox_bin("lennox-perf"), "status"], got_perf)

        def got_server(ok, out, _err):
            try:
                info = json.loads(out) if ok else None
            except ValueError:
                info = None
            if not isinstance(info, dict):
                self.server_row.value_label.set_label(out.strip() or "No server set")
            elif not info.get("online"):
                self.server_row.value_label.set_label("Offline or unreachable")
            else:
                names = ", ".join(info.get("names") or [])
                ping = f" · {info['latency']} ms" if info.get("latency") is not None else ""
                self.server_row.value_label.set_label(
                    f"{info['players']} / {info['max']} online{ping}" + (f"\n{names}" if names else ""))

        run_async([lennox_bin("lennox-mcserver"), "status"], got_server)

    def _copy_option(self):
        Gdk.Display.get_default().get_clipboard().set(STEAM_OPTION)
        self.ctx.toast("Copied: paste it into the game's Launch options in Steam")

    def _on_perf(self, row, _param):
        if self.updating:
            return
        index = row.get_selected()
        if 0 <= index < len(PERF_MODES):
            run_async([lennox_bin("lennox-perf"), PERF_MODES[index][0]])

    def _open_clips(self):
        folder = os.path.expanduser(self.ctx.store.get("clips.folder") or "~/Videos/Clips")
        os.makedirs(folder, exist_ok=True)
        launch(["xdg-open", folder])
