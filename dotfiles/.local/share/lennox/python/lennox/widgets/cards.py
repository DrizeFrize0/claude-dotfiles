"""The widget cards, used on the desktop and in the dashboard.

Every card has start() and stop(): timers only run while the card is on
screen, and slow work (network, D-Bus, commands) runs in a thread so the
widgets never freeze.
"""

import datetime
import os
import subprocess
import threading

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from . import data
from .mpris import Mpris

BIN = os.path.expanduser("~/.local/bin")


def in_thread(work, done):
    """Run work() in a thread, then done(result) on the GTK main loop."""
    def runner():
        try:
            result = work()
        except Exception as e:  # noqa: BLE001 - a card must never take the widgets down
            result = e
        GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=runner, daemon=True).start()


def launch(command, delay=0.0):
    """Start a command detached from the widgets (lennox-* commands by name)."""
    env = dict(os.environ, PATH=f"{BIN}:{os.environ.get('PATH', '')}")
    if delay:
        command = ["sh", "-c", f'sleep {delay}; exec "$@"', "lennox"] + list(command)
    try:
        subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def icon(names, size=16):
    """An icon from the first name the icon theme has (themes differ)."""
    if isinstance(names, str):
        names = [names]
    return Gtk.Image(gicon=Gio.ThemedIcon.new_from_names(list(names)), pixel_size=size)


def label(text="", classes=(), xalign=0.0, **kwargs):
    widget = Gtk.Label(label=text, xalign=xalign, **kwargs)
    for c in classes:
        widget.add_css_class(c)
    return widget


def icon_button(icon, tooltip, callback, classes=("icon-button",)):
    button = Gtk.Button(icon_name=icon, tooltip_text=tooltip, valign=Gtk.Align.CENTER)
    for c in classes:
        button.add_css_class(c)
    button.connect("clicked", lambda _b: callback())
    return button


class Card(Gtk.Box):
    """Base: a rounded box with an optional title."""

    def __init__(self, title=None, framed=True, spacing=10):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        if framed:
            self.add_css_class("card")
        if title:
            self.append(label(title.upper(), ("card-title",)))
        self._timers = []
        self.running = False

    def every(self, seconds, callback):
        """Call callback now and every `seconds` while the card runs."""
        def tick():
            if not self.running:
                return GLib.SOURCE_REMOVE
            callback()
            return GLib.SOURCE_CONTINUE
        self._timers.append((seconds, tick))

    def start(self):
        if self.running:
            return
        self.running = True
        self._sources = []
        for seconds, tick in self._timers:
            tick()
            self._sources.append(GLib.timeout_add(int(seconds * 1000), tick))

    def stop(self):
        self.running = False
        for source in getattr(self, "_sources", []):
            GLib.source_remove(source)
        self._sources = []


# ---------------------------------------------------------------- clock

class ClockCard(Card):
    def __init__(self, store, framed=False, greeting=True):
        super().__init__(framed=framed, spacing=2)
        self.store = store
        self.show_greeting = greeting
        row = Gtk.Box(spacing=8)
        self.time = label(classes=("clock-time",))
        self.ampm = label(classes=("clock-ampm",), valign=Gtk.Align.END)
        row.append(self.time)
        row.append(self.ampm)
        self.date = label(classes=("clock-date",))
        self.greeting = label(classes=("clock-greeting",))
        self.append(row)
        self.append(self.date)
        self.append(self.greeting)
        self._shown = None
        self.every(1, self.refresh)

    def refresh(self, force=False):
        now = datetime.datetime.now()
        h24 = self.store.get("bar.clock_24h")
        key = (now.strftime("%Y%m%d%H%M"), h24)
        if key == self._shown and not force:
            return
        self._shown = key
        self.time.set_label(data.format_time(now, h24))
        self.ampm.set_label("" if h24 else now.strftime("%p"))
        self.ampm.set_visible(not h24)
        self.date.set_label(data.format_date(now))
        name = data.display_name(self.store.get("widgets.name"))
        text = data.greeting(now.hour)
        self.greeting.set_label(f"{text}, {name}" if name else text)
        self.greeting.set_visible(self.show_greeting)


# ---------------------------------------------------------------- weather

class WeatherCard(Card):
    def __init__(self, store, detailed=False, hide_on_error=False):
        super().__init__("Weather" if detailed else None)
        self.store = store
        self.detailed = detailed
        self.hide_on_error = hide_on_error
        self._busy = False
        self._last_ok = 0.0

        top = Gtk.Box(spacing=14)
        self.icon = Gtk.Image(pixel_size=48, icon_name="weather-few-clouds-symbolic")
        self.icon.add_css_class("weather-icon")
        top.append(self.icon)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.temp = label(classes=("weather-temp",))
        self.desc = label(classes=("dim",), ellipsize=Pango.EllipsizeMode.END, max_width_chars=28)
        text.append(self.temp)
        text.append(self.desc)
        top.append(text)
        self.append(top)

        self.days = Gtk.Box(spacing=8, homogeneous=True)
        self.days.set_visible(False)
        self.append(self.days)

        self.message = label(classes=("dim", "small"), wrap=True)
        self.message.set_visible(False)
        self.append(self.message)
        self.every(10 * 60, self.refresh)

    def refresh(self, force=False):
        if self._busy:
            return
        city = self.store.get("widgets.weather_city")
        unit = self.store.get("widgets.temperature_unit")
        self._busy = True
        in_thread(lambda: data.weather(city, unit, force=force), self._show)

    def _show(self, result):
        self._busy = False
        if isinstance(result, Exception):
            message = str(result) if isinstance(result, data.WeatherError) else "Weather is unavailable"
            self.message.set_label(message)
            self.message.set_visible(True)
            self.icon.set_from_icon_name("weather-severe-alert-symbolic")
            self.temp.set_label("")
            self.desc.set_label("")
            self.days.set_visible(False)
            if self.hide_on_error:
                self.set_visible(False)
            return
        self.set_visible(True)
        self.message.set_visible(bool(result.get("stale")))
        self.message.set_label("Offline: showing the last forecast")
        self.icon.set_from_icon_name(result["icon"])
        self.temp.set_label(f"{result['temp']}{result['unit']}")
        self.desc.set_label(f"{result['text']} · {result['place']}")
        self.desc.set_tooltip_text(f"Feels like {result['feels']}{result['unit']}")
        child = self.days.get_first_child()
        while child:
            self.days.remove(child)
            child = self.days.get_first_child()
        for day in result["days"]:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.add_css_class("weather-day")
            box.append(label(day["name"], ("small", "dim"), xalign=0.5))
            box.append(Gtk.Image(icon_name=day["icon"], pixel_size=22, tooltip_text=day["text"]))
            box.append(label(f"{day['high']}° / {day['low']}°", ("small",), xalign=0.5))
            self.days.append(box)
        self.days.set_visible(self.detailed and bool(result["days"]))


# ---------------------------------------------------------------- media

class MediaCard(Card):
    ART = 64

    def __init__(self, mpris=None, hide_when_idle=True, title=None):
        super().__init__(title)
        self.mpris = mpris or Mpris()
        self.hide_when_idle = hide_when_idle
        self.player = None
        self._busy = False
        self._art_url = None

        row = Gtk.Box(spacing=14)
        self.art_stack = Gtk.Stack()
        self.art_stack.set_size_request(self.ART, self.ART)
        self.art_stack.set_overflow(Gtk.Overflow.HIDDEN)
        self.art_stack.add_css_class("media-art")
        placeholder = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=28)
        self.art_stack.add_named(placeholder, "none")
        self.art = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        self.art.set_size_request(self.ART, self.ART)
        self.art_stack.add_named(self.art, "art")
        row.append(self.art_stack)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True, spacing=2)
        self.title = label(classes=("media-title",), ellipsize=Pango.EllipsizeMode.END, max_width_chars=22)
        self.artist = label(classes=("dim",), ellipsize=Pango.EllipsizeMode.END, max_width_chars=24)
        text.append(self.title)
        text.append(self.artist)
        row.append(text)
        self.append(row)

        buttons = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.prev = icon_button("media-skip-backward-symbolic", "Previous", lambda: self._command("Previous"),
                                ("media-button",))
        self.play = icon_button("media-playback-start-symbolic", "Play / pause", lambda: self._command("PlayPause"),
                                ("media-button", "play"))
        self.next = icon_button("media-skip-forward-symbolic", "Next", lambda: self._command("Next"),
                                ("media-button",))
        for b in (self.prev, self.play, self.next):
            buttons.append(b)
        self.buttons = buttons
        self.append(buttons)
        self._show(None)
        self.every(2, self.refresh)

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        in_thread(self.mpris.now_playing, self._show)

    def _show(self, info):
        self._busy = False
        if isinstance(info, Exception):
            info = None
        self.player = info["player"] if info else None
        if not info:
            self.set_visible(not self.hide_when_idle)
            self.title.set_label("Nothing playing")
            self.artist.set_label("Music and videos show up here")
            self.buttons.set_visible(False)
            self.art_stack.set_visible_child_name("none")
            self._art_url = None
            return
        self.set_visible(True)
        self.buttons.set_visible(True)
        self.title.set_label(info["title"])
        self.title.set_tooltip_text(info["title"])
        self.artist.set_label(info["artist"] or info["album"] or "")
        self.play.set_icon_name("media-playback-pause-symbolic" if info["playing"] else "media-playback-start-symbolic")
        self.prev.set_sensitive(info["can_prev"])
        self.next.set_sensitive(info["can_next"])
        if info["art"] != self._art_url:
            self._art_url = info["art"]
            url = info["art"]
            in_thread(lambda: data.art_file(url), lambda path: self._set_art(url, path))

    def _set_art(self, url, path):
        if url != self._art_url:
            return  # the song changed while the cover downloaded
        if isinstance(path, str):
            try:
                texture = Gdk.Texture.new_from_filename(path)
            except GLib.Error:
                texture = None
            if texture is not None:
                self.art.set_paintable(texture)
                self.art_stack.set_visible_child_name("art")
                return
        self.art_stack.set_visible_child_name("none")

    def _command(self, method):
        if self.player:
            player = self.player
            in_thread(lambda: self.mpris.command(player, method), lambda _r: self.refresh())


# ---------------------------------------------------------------- system

class _Meter(Gtk.Box):
    def __init__(self, icons, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        top = Gtk.Box(spacing=8)
        top.append(icon(icons))
        top.append(label(name, hexpand=True))
        self.value = label(classes=("dim", "small"), xalign=1.0)
        top.append(self.value)
        self.bar = Gtk.LevelBar(min_value=0, max_value=100)
        self.bar.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_LOW)
        self.bar.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_HIGH)
        self.bar.remove_offset_value(Gtk.LEVEL_BAR_OFFSET_FULL)
        self.append(top)
        self.append(self.bar)

    def show(self, percent, text, warn=80, critical=92, reverse=False):
        percent = max(0.0, min(100.0, percent))
        self.bar.set_value(percent)
        self.value.set_label(text)
        level = 100 - percent if reverse else percent
        for c in ("warning", "critical"):
            self.bar.remove_css_class(c)
        if level >= critical:
            self.bar.add_css_class("critical")
        elif level >= warn:
            self.bar.add_css_class("warning")


class SystemCard(Card):
    def __init__(self, title="System"):
        super().__init__(title)
        self.cpu_meter = data.CpuMeter()
        self.cpu = _Meter(["cpu-symbolic", "processor-symbolic", "computer-symbolic"], "Processor")
        self.mem = _Meter(["memory-symbolic", "media-memory-symbolic", "media-flash-symbolic"], "Memory")
        self.disk = _Meter(["drive-harddisk-symbolic"], "Disk")
        self.bat = _Meter(["battery-good-symbolic", "battery-symbolic"], "Battery")
        self.temp = _Meter(["temperature-symbolic", "sensors-temperature-symbolic", "weather-clear-symbolic"],
                           "Temperature")
        for m in (self.cpu, self.mem, self.disk, self.bat, self.temp):
            self.append(m)
        self.every(3, self.refresh)

    def refresh(self):
        cpu = self.cpu_meter.percent()
        self.cpu.set_visible(cpu is not None)
        if cpu is not None:
            self.cpu.show(cpu, f"{cpu:.0f}%")
        mem = data.memory()
        self.mem.set_visible(mem is not None)
        if mem:
            self.mem.show(mem[0], f"{mem[1]:.1f} / {mem[2]:.0f} GB")
        disk = data.disk("/")
        self.disk.set_visible(disk is not None)
        if disk:
            self.disk.show(disk[0], f"{disk[1]:.0f} GB free", warn=85, critical=95)
        bat = data.battery()
        self.bat.set_visible(bat is not None)
        if bat:
            percent, status = bat
            charging = status in ("Charging", "Full")
            self.bat.show(percent, f"{percent}%{' · charging' if status == 'Charging' else ''}",
                          warn=80, critical=90 if not charging else 101, reverse=True)
        temp = data.temperature()
        self.temp.set_visible(temp is not None)
        if temp is not None:
            self.temp.show(temp, f"{temp:.0f} °C", warn=80, critical=92)


# ---------------------------------------------------------------- dashboard-only cards

class HeaderCard(Card):
    def __init__(self, store, close):
        super().__init__(framed=False)
        self.store = store
        row = Gtk.Box(spacing=12)
        self.avatar = Gtk.Stack()
        self.avatar.set_size_request(52, 52)
        self.avatar.set_overflow(Gtk.Overflow.HIDDEN)
        self.avatar.add_css_class("avatar")
        self.initial = label(xalign=0.5)
        self.avatar.add_named(self.initial, "initial")
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER)
        self.avatar.add_named(self.picture, "picture")
        row.append(self.avatar)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        self.name = label(classes=("profile-name",), ellipsize=Pango.EllipsizeMode.END)
        self.uptime = label(classes=("dim", "small"))
        text.append(self.name)
        text.append(self.uptime)
        row.append(text)

        def go(cmd, delay=0.0):
            close()
            launch(cmd, delay)
        row.append(icon_button("emblem-system-symbolic", "Lennox Settings", lambda: go(["lennox-settings"])))
        row.append(icon_button("system-lock-screen-symbolic", "Lock", lambda: go(["lennox-power", "lock"], 0.3)))
        row.append(icon_button("system-shutdown-symbolic", "Power menu", lambda: go(["lennox-menu", "power"], 0.3),
                               ("icon-button", "danger")))
        self.append(row)
        self.every(60, self.refresh)

    def refresh(self):
        name = data.display_name(self.store.get("widgets.name"))
        self.name.set_label(name or "Lennox")
        self.initial.set_label((name or "L")[:1].upper())
        self.uptime.set_label(data.uptime())
        path = data.avatar_path()
        texture = None
        if path:
            try:
                texture = Gdk.Texture.new_from_filename(path)
            except GLib.Error:
                texture = None
        if texture is not None:
            self.picture.set_paintable(texture)
            self.avatar.set_visible_child_name("picture")
        else:
            self.avatar.set_visible_child_name("initial")


ACTIONS = [
    ("applets-screenshooter-symbolic", "Screenshot", ["lennox-screenshot", "area"], 0.4),
    (["color-select-symbolic", "color-picker-symbolic"], "Color picker", ["lennox-colorpicker"], 0.4),
    ("preferences-desktop-wallpaper-symbolic", "Wallpaper", ["lennox-menu", "wallpaper"], 0.2),
    (["media-playlist-shuffle-symbolic", "view-refresh-symbolic"], "Shuffle wallpaper",
     ["lennox-wallpaper", "--random"], 0.0),
    (["night-light-symbolic", "weather-clear-night-symbolic"], "Night light", ["lennox-nightlight", "toggle"], 0.0),
    (["input-gaming-symbolic", "applications-games-symbolic"], "Game mode", ["lennox-mode", "game", "toggle"], 0.0),
    (["dark-mode-symbolic", "weather-clear-night-symbolic"], "Dark / light", ["lennox-theme", "toggle"], 0.0),
    ("edit-paste-symbolic", "Clipboard", ["lennox-menu", "clipboard"], 0.2),
]


class ActionsCard(Card):
    def __init__(self, close):
        super().__init__("Quick actions")
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        for i, (icon_names, name, command, delay) in enumerate(ACTIONS):
            button = Gtk.Button(tooltip_text=name)
            button.add_css_class("action")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.append(icon(icon_names, 22))
            box.append(label(name, xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER,
                             max_width_chars=10))
            button.set_child(box)
            button.connect("clicked", self._clicked, command, delay, close)
            grid.attach(button, i % 4, i // 4, 1, 1)
        self.append(grid)

    @staticmethod
    def _clicked(_button, command, delay, close):
        close()
        launch(command, delay)


class SlidersCard(Card):
    """Volume and screen brightness."""

    def __init__(self):
        super().__init__("Sound and screen")
        self._updating = False
        self._pending = {}
        self.mute = icon_button("audio-volume-high-symbolic", "Mute", self._toggle_mute)
        self.volume = self._scale()
        self.volume.connect("value-changed", self._changed, "volume")
        self.append(self._row(self.mute, self.volume))
        bright_icon = icon(["display-brightness-symbolic", "brightness-symbolic"], 18)
        bright_icon.set_size_request(38, 38)
        self.brightness = self._scale()
        self.brightness.connect("value-changed", self._changed, "brightness")
        self.bright_row = self._row(bright_icon, self.brightness)
        self.append(self.bright_row)
        self.every(5, self.refresh)

    @staticmethod
    def _scale():
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, draw_value=False)
        scale.set_range(0, 100)
        scale.set_increments(5, 10)
        return scale

    @staticmethod
    def _row(icon, scale):
        row = Gtk.Box(spacing=10)
        row.append(icon)
        row.append(scale)
        return row

    @staticmethod
    def _read():
        volume = muted = brightness = None
        try:
            out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True,
                                 text=True, timeout=2).stdout.split()
            if len(out) >= 2 and out[0] == "Volume:":
                volume = round(float(out[1]) * 100)
                muted = "[MUTED]" in out
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        try:
            out = subprocess.run([os.path.join(BIN, "lennox-panel"), "get", "brightness"], capture_output=True,
                                 text=True, timeout=2)
            if out.returncode == 0 and out.stdout.strip():
                brightness = int(out.stdout.strip())
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            pass
        return volume, muted, brightness

    def refresh(self):
        if self._pending:
            return  # don't jump the slider while you drag it
        in_thread(self._read, self._show)

    def _show(self, result):
        if isinstance(result, Exception):
            return
        volume, muted, brightness = result
        self._updating = True
        self.volume.set_sensitive(volume is not None)
        self.mute.set_sensitive(volume is not None)
        if volume is not None:
            self.volume.set_value(min(volume, 100))
            self.mute.set_icon_name("audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic")
        self.bright_row.set_visible(brightness is not None)
        if brightness is not None:
            self.brightness.set_value(brightness)
        self._updating = False

    def _changed(self, scale, what):
        if self._updating:
            return
        if what in self._pending:
            GLib.source_remove(self._pending[what])
        self._pending[what] = GLib.timeout_add(120, self._commit, what)

    def _commit(self, what):
        self._pending.pop(what, None)
        if what == "volume":
            value = int(self.volume.get_value())
            launch(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{value}%"])
        else:
            value = max(2, int(self.brightness.get_value()))
            launch([os.path.join(BIN, "lennox-panel"), "set", "brightness", str(value)])
        return GLib.SOURCE_REMOVE

    def _toggle_mute(self):
        launch(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
        GLib.timeout_add(250, lambda: (self.refresh(), False)[1])


class CalendarCard(Card):
    def __init__(self):
        super().__init__("Calendar")
        self.calendar = Gtk.Calendar()
        self.append(self.calendar)
        self.every(60, self.refresh)

    def refresh(self):
        today = GLib.DateTime.new_now_local()
        self.calendar.select_day(today)


class NotesCard(Card):
    def __init__(self):
        super().__init__("Notes")
        frame = Gtk.ScrolledWindow(min_content_height=120, max_content_height=240, propagate_natural_height=True)
        frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        frame.add_css_class("notes-frame")
        self.view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.view.add_css_class("notes")
        self.buffer = self.view.get_buffer()
        self.buffer.set_text(data.load_notes())
        self.buffer.connect("changed", self._changed)
        frame.set_child(self.view)
        self.append(frame)
        self.append(label("Saved automatically", ("dim", "small")))
        self._save_source = 0

    def _changed(self, _buffer):
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(800, self._save)

    def _save(self):
        self._save_source = 0
        start, end = self.buffer.get_bounds()
        data.save_notes(self.buffer.get_text(start, end, True))
        return GLib.SOURCE_REMOVE

    def start(self):
        # Pick up edits made elsewhere (e.g. in a text editor) while closed
        start, end = self.buffer.get_bounds()
        on_disk = data.load_notes()
        if on_disk != self.buffer.get_text(start, end, True) and not self._save_source:
            self.buffer.set_text(on_disk)
            if self._save_source:  # set_text fired "changed": nothing new to save
                GLib.source_remove(self._save_source)
                self._save_source = 0
        super().start()

    def stop(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save()
        super().stop()
