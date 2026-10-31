"""Game center: clips, performance, launchers, the FPS overlay and your Minecraft server."""

import json
import os

from gi.repository import Adw, Gdk, GLib, Gtk

from ... import gameprofiles as GP
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

        self.profiles_group = Adw.PreferencesGroup(
            title="Per-game settings",
            description="Each game can have its own performance mode, quiet notifications and no night light "
                        "while it's open. Everything goes back when you close it.")
        self.profiles_group.add(rows.switch_row(store, "games.profiles", "Use per-game settings"))
        self.profile_rows = []
        self.open_windows = []
        self.add_row = Adw.ComboRow(title="Add an open game", subtitle="Open the game first, then pick its window")
        add_button = Gtk.Button(label="Add", valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
        add_button.connect("clicked", lambda _b: self._add_open())
        self.add_row.add_suffix(add_button)
        self.profiles_group.add(self.add_row)
        self.type_row = Adw.EntryRow(title="Or type its name (as it appears in the window)")
        self.type_row.set_show_apply_button(True)
        self.type_row.connect("apply", lambda r: self._add_named(r.get_text()))
        self.profiles_group.add(self.type_row)
        page.add(self.profiles_group)

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

    # ------------------------------------------------------------ per-game settings

    def _refresh_profiles(self):
        for row in self.profile_rows:
            self.profiles_group.remove(row)
        self.profile_rows = []
        for profile in GP.load():
            row = Adw.ExpanderRow(title=GLib.markup_escape_text(profile["name"]),
                                  subtitle=self._summary(profile))
            row.add_prefix(Gtk.Image.new_from_icon_name("input-gaming-symbolic"))
            perf = Adw.ComboRow(title="Performance")
            labels = ["Leave as it is", "Quiet", "Balanced", "Max performance"]
            perf.set_model(Gtk.StringList.new(labels))
            perf.set_selected(GP.PERF_MODES.index(profile["perf"]))
            perf.connect("notify::selected", lambda r, _p, m=profile["match"]: self._edit(
                m, perf=GP.PERF_MODES[r.get_selected()]))
            row.add_row(perf)
            for key, title in (("dnd", "Hold notifications"), ("nightlight_off", "Turn the night light off")):
                switch = Adw.SwitchRow(title=title, active=profile[key])
                switch.connect("notify::active", lambda r, _p, m=profile["match"], k=key: self._edit(
                    m, **{k: r.get_active()}))
                row.add_row(switch)
            remove = rows.button_row("Remove this game", f"Matches windows containing “{profile['match']}”",
                                     "Remove", lambda m=profile["match"]: self._remove(m), "edit-delete-symbolic")
            row.add_row(remove)
            self.profiles_group.add(row)
            self.profile_rows.append(row)
        run_async(["hyprctl", "clients", "-j"], self._got_windows)

    @staticmethod
    def _summary(profile):
        parts = [{"": "performance unchanged", "quiet": "quiet", "balanced": "balanced",
                  "max": "max performance"}[profile["perf"]]]
        if profile["dnd"]:
            parts.append("notifications held")
        if profile["nightlight_off"]:
            parts.append("no night light")
        return ", ".join(parts)

    def _got_windows(self, ok, out, _err):
        try:
            clients = json.loads(out) if ok else []
        except ValueError:
            clients = []
        classes = sorted({c.get("class") for c in clients if c.get("class") and not c["class"].startswith(
            ("dev.lennox", "lennox", "kitty", "rofi", "waybar"))})
        self.open_windows = classes
        self.add_row.set_model(Gtk.StringList.new(classes or ["(no windows open)"]))
        self.add_row.set_sensitive(bool(classes))

    def _changed(self, message=None):
        if message:
            self.ctx.toast(message)
        run_async([lennox_bin("lennox-gameprofile"), "check"])
        self._refresh_profiles()

    def _add_open(self):
        index = self.add_row.get_selected()
        if 0 <= index < len(self.open_windows):
            self._add_named(self.open_windows[index])

    def _add_named(self, name):
        name = name.strip()
        profiles = GP.load()
        updated = GP.add(profiles, name)
        if len(updated) == len(profiles):
            self.ctx.toast("That game is already added" if name else "Type the game's name first")
            return
        GP.save(updated)
        self.type_row.set_text("")
        self._changed(f"{name}: max performance, notifications held, no night light. Change it below")

    def _edit(self, match, **changes):
        profiles = GP.load()
        for profile in profiles:
            if profile["match"] == match:
                profile.update(changes)
        GP.save(profiles)
        for row, profile in zip(self.profile_rows, profiles):
            row.set_subtitle(self._summary(profile))
        run_async([lennox_bin("lennox-gameprofile"), "check"])

    def _remove(self, match):
        GP.save([p for p in GP.load() if p["match"] != match])
        self._changed("Removed")

    def refresh(self):
        self._refresh_profiles()
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
