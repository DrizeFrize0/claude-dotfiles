"""Extras: pet, music wallpaper, cursor effects, screensaver, lyrics, seasons, profiles, fan, Discord, downloads, Ask Claude, games, boot."""

import json

from gi.repository import Adw

from ... import autoprofile as AP
from .. import rows
from ..util import have, lennox_bin, run_async


def terminal(command):
    """Run a command in a terminal window (for the things that ask questions)."""
    run_async(["kitty", "--hold", "bash", "-c", command])


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        store = ctx.store
        page = Adw.PreferencesPage()

        look = Adw.PreferencesGroup(title="On your desktop", description="Little extras. Each one has its own switch and costs almost nothing while it is off.")
        look.add(rows.switch_row(store, "pet.on", "Desktop pet", "A small cat walks along the bottom of the screen and sleeps while you focus or are away"))
        look.add(rows.switch_row(store, "visualizer.on", "Music wallpaper",
                                 "The bottom of the desktop pulses with what's playing (needs cava: lennox upgrade installs it)"))
        look.add(rows.switch_row(store, "cursorfx.on", "Cursor effects", "A glowing trail, or a spotlight for screen sharing"))
        look.add(rows.combo_row(store, "cursorfx.style", "Cursor style", [("trail", "Glowing trail"), ("spotlight", "Spotlight")]))
        look.add(rows.switch_row(store, "cursorfx.ripple", "Ring on every click"))
        look.add(rows.switch_row(store, "lyrics.on", "Lyrics in the island", "Synced lyrics scroll under the song title (from lrclib.net)"))
        page.add(look)

        saver = Adw.PreferencesGroup(title="Screensaver", description="A calm animation after a few idle minutes, before the screen locks. Any key closes it.")
        saver.add(rows.switch_row(store, "screensaver.on", "Screensaver"))
        saver.add(rows.spin_row(store, "screensaver.minutes", "Start after", "Idle minutes (before the lock time in Power)", lower=1, upper=60))
        saver.add(rows.combo_row(store, "screensaver.style", "Style", [("stars", "Stars"), ("rain", "Rain on glass"), ("aurora", "Aurora")]))
        saver.add(rows.button_row("Try it", "Shows it for 6 seconds", "Preview",
                                  lambda: run_async([lennox_bin("lennox-screensaver"), store.get("screensaver.style"), "--seconds", "6"])))
        page.add(saver)

        season = Adw.PreferencesGroup(
            title="Theme of the season", description="Colors change for the occasions you pick, then go back. Add pictures to "
            "~/.config/lennox/seasons/ramadan (or eid, halloween, newyear, jordan_day) for a wallpaper too. Ramadan and Eid dates can be a day off the moon sighting.")
        season.add(rows.switch_row(store, "seasons.on", "Follow the occasions"))
        for key, title in (("ramadan", "Ramadan"), ("eid", "Eid"), ("halloween", "Halloween"), ("newyear", "New Year"), ("jordan_day", "Independence Day (25 May)")):
            season.add(rows.switch_row(store, f"seasons.{key}", title))
        page.add(season)

        more = Adw.PreferencesGroup(title="Little helpers", description="Each one is off until you switch it on.")
        more.add(rows.switch_row(store, "musiccolors.on", "Colors from your music",
                                 "The desktop colors follow the cover of the song that is playing and come back a minute and a half after the music stops. "
                                 "Each change reloads the colors for a moment"))
        more.add(rows.switch_row(store, "dynwall.on", "Wallpaper that follows the day",
                                 "Dawn, day, evening and night pictures, and a moody one when it rains in your city (uses the Lennox wallpapers in Settings > Wallpaper)"))
        more.add(rows.switch_row(store, "tidy.on", "Tidy my downloads",
                                 "New files go into folders inside Downloads (Images, Documents, Archives, Installers, Minecraft...) once they have finished downloading"))
        more.add(rows.button_row("Tidy now", "Sorts what is in Downloads right now", "Tidy", lambda: run_async([lennox_bin("lennox-tidy"), "run", "--now"])))
        more.add(rows.button_row("Undo the last tidy", "Puts the last batch of files back where they were", "Undo", lambda: run_async([lennox_bin("lennox-tidy"), "undo"])))
        page.add(more)

        daily = Adw.PreferencesGroup(title="Wallpaper of the day")
        daily.add(rows.switch_row(store, "wallpaper.daily", "A new wallpaper every morning", "Takes turns through your wallpapers"))
        daily.add(rows.entry_row(store, "wallpaper.daily_folder", "Folder (empty: your Lennox wallpapers)"))
        daily.add(rows.button_row("Change it now", None, "Change", lambda: run_async(["python3", "-m", "lennox.wotd"])))
        page.add(daily)

        auto = Adw.PreferencesGroup(
            title="Profiles by place or time",
            description='Rules like  wifi:School -> quiet dnd volume=20  or  time:22:00-06:00 -> quiet night=on.  '
                        "Words: quiet, balanced, max, dnd, volume=N, night=on or off. When no rule fits, everything goes back.")
        auto.add(rows.switch_row(store, "auto.on", "Use profiles"))
        auto.add(self._rule_entry())
        self.auto_group = auto
        self.rule_rows = []
        page.add(auto)

        fan = Adw.PreferencesGroup(title="Fan and noise", description="Cool holds the processor to 80%: the short spikes to 98 degrees stop and you will barely feel it. Silent is quieter still (60%, turbo off). Turbo is for games.")
        fan.add(rows.combo_row(store, "fan.profile", "Profile", [("silent", "Silent"), ("cool", "Cool (trims heat spikes)"), ("normal", "Normal"), ("turbo", "Turbo")]))
        self.fan_row = rows.info_row("Right now", "…")
        fan.add(self.fan_row)
        page.add(fan)

        online = Adw.PreferencesGroup(title="Online")
        online.add(rows.entry_row(store, "discord.server_id", "Discord server ID (turn on its widget in Server Settings > Widget)"))
        online.add(rows.switch_row(store, "downloads.on", "Downloads in the bar", "Progress of browser downloads; a click opens the finished file"))
        online.add(rows.entry_row(store, "downloads.folder", "Downloads folder (empty: ~/Downloads)"))
        page.add(online)

        claude = Adw.PreferencesGroup(
            title="Ask Claude", description="SUPER + SHIFT + A opens a small box anywhere. It uses an API key from "
            "ANTHROPIC_API_KEY or the file ~/.config/lennox/anthropic.key (one line), or else Claude Code if it is installed.")
        claude.add(rows.entry_row(store, "ask.model", "Model"))
        claude.add(rows.button_row("Ask now", None, "Open", lambda: run_async([lennox_bin("lennox-ask")])))
        page.add(claude)

        fun = Adw.PreferencesGroup(title="A break", description="SUPER + SHIFT + G. Arrow keys or WASD, R to retry, Esc to close.")
        fun.add(rows.button_row("Snake", None, "Play", lambda: run_async([lennox_bin("lennox-minigame"), "snake"])))
        fun.add(rows.button_row("Flappy", None, "Play", lambda: run_async([lennox_bin("lennox-minigame"), "flappy"])))
        page.add(fun)

        boot = Adw.PreferencesGroup(
            title="Startup animation", description="A Lennox animation while the computer starts. It changes how the computer boots, so it "
            "shows you exactly what it will change first and keeps backups. Needs the plymouth package (it installs it).")
        boot.add(rows.button_row("See what it would change", "Changes nothing", "Show",
                                 lambda: terminal(f"{lennox_bin('lennox-boot-animation')} plan; echo; read -rp 'Press Enter to close'")))
        boot.add(rows.button_row("Turn it on", "Asks before it does anything", "Turn on",
                                 lambda: terminal(f"B={lennox_bin('lennox-boot-animation')}; $B plan; read -rp 'Go ahead? [y/N] ' a; "
                                                  "[[ $a == [yY]* ]] && $B enable --yes; read -rp 'Press Enter to close'")))
        boot.add(rows.button_row("Turn it off", "Puts the old startup back", "Turn off",
                                 lambda: terminal(f"{lennox_bin('lennox-boot-animation')} disable --yes; read -rp 'Press Enter to close'")))
        page.add(boot)
        self.widget = page
        self.have_cava = have("cava")

    def _rule_entry(self):
        row = Adw.EntryRow(title="Add a rule", show_apply_button=True)

        def apply(r):
            text = r.get_text().strip()
            if AP.parse_rule(text) is None:
                r.add_css_class("error")
                return
            r.remove_css_class("error")
            run_async([lennox_bin("lennox-autoprofile"), "add", text], lambda ok, _o, _e: (r.set_text(""), self.refresh()))
        row.connect("apply", apply)
        return row

    def refresh(self):
        run_async([lennox_bin("lennox-autoprofile"), "list"], self._got_rules)
        run_async([lennox_bin("lennox-fan"), "status"], self._got_fan)

    def _got_rules(self, ok, out, _err):
        try:
            rules = json.loads(out) if ok else []
        except ValueError:
            rules = []
        for row in self.rule_rows:
            self.auto_group.remove(row)
        self.rule_rows = []
        from gi.repository import Gtk
        for i, rule in enumerate(rules):
            row = Adw.ActionRow(title=AP.describe(rule), use_markup=False)
            button = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Remove")
            button.add_css_class("flat")
            button.connect("clicked", lambda _b, n=i: run_async([lennox_bin("lennox-autoprofile"), "remove", str(n)],
                                                                 lambda *_a: self.refresh()))
            row.add_suffix(button)
            self.auto_group.add(row)
            self.rule_rows.append(row)

    def _got_fan(self, ok, out, _err):
        try:
            st = json.loads(out) if ok else None
        except ValueError:
            st = None
        if not st:
            return
        parts = [f"{st['temp']:.0f}°C" if st.get("temp") else "temperature unknown",
                 (f"fan {max(st['fans'])} rpm" if st.get("fans") else "fan speed not reported by this laptop")]
        if st.get("cap") is not None:
            parts.append(f"processor limit {st['cap']}%")
        self.fan_row.value_label.set_label(" · ".join(parts))
