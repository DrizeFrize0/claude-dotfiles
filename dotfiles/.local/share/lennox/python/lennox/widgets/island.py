"""The dynamic island: a pill under the bar that grows to show what's happening.

What it shows, most important first:
    ringing   an alarm or timer going off (Snooze / Stop), even over fullscreen apps
    event     a few seconds of news: a notification, charging, Wi-Fi or Bluetooth
              connecting, a clip saved (`lennox-widgets island event ICON TEXT`)
    call      an app is using the microphone (with how long)
    timer     the next timer, or a reminder / alarm less than 10 minutes away
    music     what's playing (controls when you hover)
Nothing to show: it hides and takes no space.

The same process fires timers, alarms and reminders (lennox.clock), so they
work with the Clock app closed.
"""

import copy
import glob
import json
import math
import os
import subprocess
import threading
import time

from gi.repository import Gio, GLib, Gtk, Pango

from .. import clock as C
from . import data

EVENT_SECONDS = 4
SOON = 10 * 60            # reminders / alarms show this long before they're due
RING_LIMIT = 2 * 60       # an unanswered alarm stops ringing after 2 minutes
SOUNDS = ["/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
          "/usr/share/sounds/freedesktop/stereo/complete.oga",
          "/usr/share/sounds/freedesktop/stereo/bell.oga"]
REMINDER_SOUND = "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"


def notify(title, body, urgency="normal", icon="alarm-symbolic"):
    try:
        subprocess.Popen(["notify-send", "-a", "Lennox", "-u", urgency, "-i", icon, title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def play(path):
    for player in (["pw-play"], ["paplay"]):
        try:
            return subprocess.Popen(player + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            continue
    return None


# ---------------------------------------------------------------- what to show

def choose(state, now):
    """Pick what the island shows: (kind, info) or None. Pure, so it can be tested."""
    ringing = state.get("ringing") or []
    if ringing:
        return "ringing", ringing[0]
    if state.get("fullscreen"):
        return None            # games and videos: only an alarm interrupts
    event = state.get("event")
    if event and event["until"] > now:
        return "event", event
    if state.get("call_since"):
        return "call", {"since": state["call_since"]}
    up = state.get("next_up")
    if up:
        kind, item, left = up
        if kind == "timer" or left <= SOON:
            return "timer", {"kind": kind, "item": item, "left": left}
    if state.get("stopwatch_running"):
        return "stopwatch", {"elapsed": state["stopwatch_elapsed"]}
    music = state.get("music")
    if music and music.get("playing") and state.get("show_music", True):
        return "music", music
    if state.get("place") == "bar":
        return "clock", {}     # in the bar it is the clock when nothing's happening
    return None


def show_key(kind, info):
    """What makes this the same thing as last second (so buttons aren't rebuilt under the mouse)."""
    if kind == "ringing":
        return info.get("id")
    if kind == "timer":
        item = info["item"]
        return item.get("id"), item.get("paused_left") is not None
    if kind == "music":
        return info.get("player"), info.get("title")
    if kind == "event":
        return info.get("until")
    if kind == "call":
        return info.get("since")
    if kind == "clock":
        return "clock"
    return None


# ---------------------------------------------------------------- clock engine

class ClockEngine:
    """Fires due timers / alarms / reminders and rings until stopped."""

    def __init__(self, path=None, notify_fn=notify, play_fn=play):
        self.path = path
        self.notify = notify_fn
        self.play = play_fn
        self.sound = None
        self.ring_started = None

    def tick(self, now=None):
        now = now or time.time()
        data_now = C.load(self.path)
        if C.due(copy.deepcopy(data_now), now):   # only lock and save when something is due
            with C.edit(self.path) as d:
                fired = C.due(d, now)
                data_now = d
            for kind, item, missed in fired:
                self._announce(kind, item, missed)
        self._ring(data_now, now)
        return data_now

    def _announce(self, kind, item, missed):
        label = item.get("label") or item.get("text") or ""
        if kind == "reminder":
            # Critical: reminders come through do-not-disturb
            self.notify("Reminder" + (" (missed)" if missed else ""), label, "critical", "appointment-soon-symbolic")
            if not missed:
                self.play(REMINDER_SOUND)
        elif missed:
            what = "Alarm" if kind == "alarm" else "Timer"
            self.notify(f"Missed {what.lower()}", f"{label} went off while the laptop was off.")
        elif kind == "timer":
            self.notify("Time's up", label, "critical", "alarm-symbolic")
        else:
            self.notify(f"⏰ {item['time']}", label, "critical", "alarm-symbolic")

    def _ring(self, d, now):
        if not d["ringing"]:
            self.ring_started = None
            self.stop_sound()
            return
        if self.ring_started is None:
            self.ring_started = now
        if now - self.ring_started > RING_LIMIT:
            with C.edit(self.path) as dd:
                stopped = C.stop_ringing(dd)
            for item in stopped:
                self.notify("Nobody answered", f"{item['label']} stopped ringing.")
            self.ring_started = None
            self.stop_sound()
            return
        if self.sound is None or self.sound.poll() is not None:
            sound = next((s for s in SOUNDS if os.path.exists(s)), None)
            self.sound = self.play(sound) if sound else None

    def stop_sound(self):
        if self.sound is not None and self.sound.poll() is None:
            self.sound.terminate()
        self.sound = None


# ---------------------------------------------------------------- status

def mic_in_use():
    """An app (not Lennox's own clean microphone) is recording: probably a call."""
    try:
        out = subprocess.run(["pactl", "-f", "json", "list", "source-outputs"], capture_output=True,
                             text=True, timeout=2).stdout
        for stream in json.loads(out or "[]"):
            name = (stream.get("properties") or {}).get("node.name", "")
            if not name.startswith(("lennox_clean_mic", "echo-cancel")):
                return True
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return False


def on_ac(root="/sys/class/power_supply"):
    for supply in glob.glob(os.path.join(root, "*")):
        try:
            with open(os.path.join(supply, "type")) as f:
                if f.read().strip() != "Mains":
                    continue
            with open(os.path.join(supply, "online")) as f:
                return f.read().strip() == "1"
        except OSError:
            continue
    return None


def wifi_name():
    try:
        out = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
                             capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        name, _, kind = line.rpartition(":")
        if kind.endswith("wireless"):
            return name.replace("\\:", ":")
    return ""


def bluetooth_devices():
    try:
        out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True,
                             timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {line.split(" ", 2)[2] for line in out.splitlines() if line.startswith("Device ") and line.count(" ") >= 2}


def fullscreen_active():
    try:
        out = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=2).stdout
        return int((json.loads(out or "{}") or {}).get("fullscreen") or 0) in (1, 2)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        return False


def bar_geometry(path=None):
    """(top margin, height) of the running bar, so the island sits exactly in it."""
    path = path or os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "lennox", "waybar.json")
    try:
        with open(path, encoding="utf-8") as f:
            bar = json.load(f)
        return int(bar.get("margin-top") or 0), int(bar.get("height") or 34)
    except (OSError, ValueError, TypeError):
        return 6, 36


def dnd_on():
    try:
        return subprocess.run(["swaync-client", "-D"], capture_output=True, text=True,
                              timeout=2).stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


class StatusWatcher:
    """Every 2 s on a worker thread: music, call, charging, Wi-Fi, Bluetooth.
    Changes become island events; the latest values go to on_update(dict)."""

    def __init__(self, mpris, on_update, on_event):
        # Its own player watcher on its own bus connection: the dashboard's
        # (main thread) must never share state with this worker thread
        self.mpris = None
        self.use_mpris = mpris is not None
        self.on_update = on_update
        self.on_event = on_event
        self.last = {}
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        first = True
        while self.running:
            try:
                self._poll(first)
            except Exception:  # noqa: BLE001  never let the island die on a flaky tool
                pass
            first = False
            time.sleep(2)

    def _music(self):
        if not self.use_mpris:
            return None
        if self.mpris is None:
            from .mpris import Mpris
            address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            bus = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self.mpris = Mpris(bus=bus)
        return self.mpris.now_playing()

    def _poll(self, first):
        music = self._music()
        if music and music.get("art"):
            music["art_file"] = data.art_file(music["art"])
        status = {"music": music, "call": mic_in_use(), "ac": on_ac(), "wifi": wifi_name(),
                  "bt": bluetooth_devices(), "dnd": dnd_on(), "fullscreen": fullscreen_active()}
        events = [] if first else self._changes(status)
        self.last = status
        GLib.idle_add(self._deliver, status, events, priority=GLib.PRIORITY_DEFAULT)

    def _changes(self, s):
        events, old = [], self.last
        if s["ac"] is not None and old.get("ac") is not None and s["ac"] != old["ac"]:
            bat = data.battery()
            level = f" · {bat[0]}%" if bat else ""
            events.append(("battery-full-charging-symbolic", "Charging" + level) if s["ac"]
                          else ("battery-good-symbolic", "On battery" + level))
        if s["wifi"] is not None and old.get("wifi") is not None and s["wifi"] != old["wifi"]:
            events.append(("network-wireless-symbolic", f"Connected to {s['wifi']}") if s["wifi"]
                          else ("network-wireless-offline-symbolic", "Wi-Fi disconnected"))
        if s["bt"] is not None and old.get("bt") is not None:
            for name in sorted(s["bt"] - old["bt"]):
                events.append(("bluetooth-active-symbolic", f"{name} connected"))
            for name in sorted(old["bt"] - s["bt"]):
                events.append(("bluetooth-disabled-symbolic", f"{name} disconnected"))
        return events

    def _deliver(self, status, events):
        self.on_update(status)
        for icon, text in events:
            self.on_event(icon, text)
        return GLib.SOURCE_REMOVE


class NotificationWatcher:
    """New notifications (watched on the session bus, nothing is changed)."""

    RULE = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"

    def __init__(self, on_notification):
        self.on_notification = on_notification
        self.conn = None
        try:
            address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            self.conn = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                "org.freedesktop.DBus.Monitoring", "BecomeMonitor",
                                GLib.Variant("(asu)", ([self.RULE], 0)), None,
                                Gio.DBusCallFlags.NONE, 2000, None)
            self.conn.add_filter(self._filter)
        except GLib.Error:
            self.conn = None

    def _filter(self, _conn, message, incoming):
        # Runs on GDBus's worker thread: never raise, hand the result to the main loop
        try:
            body = message.get_body() if incoming and message.get_member() == "Notify" else None
            if body is not None and body.get_type_string() == "(susssasa{sv}i)":
                app, _rid, _icon, summary, _body, _actions, hints, _timeout = body.unpack()
                urgency = hints.get("urgency", 1) if isinstance(hints, dict) else 1
                GLib.idle_add(self.on_notification, app, summary, urgency, priority=GLib.PRIORITY_DEFAULT)
        except Exception:  # noqa: BLE001
            pass
        return None  # monitors only watch


# ---------------------------------------------------------------- the window

class EqBars(Gtk.Box):
    """Four little bars that dance while music plays (low and still when paused).
    Plain boxes whose height changes ~30 times a second: no cairo needed."""

    HEIGHT = 16

    def __init__(self):
        super().__init__(spacing=2, valign=Gtk.Align.CENTER, css_classes=["island-bars"])
        self.set_size_request(18, self.HEIGHT)
        self.bars = []
        for _ in range(4):
            bar = Gtk.Box(css_classes=["island-bar"], valign=Gtk.Align.CENTER)
            bar.set_size_request(3, 3)
            self.append(bar)
            self.bars.append(bar)
        self.playing = False
        self.tick = None

    def set_playing(self, playing):
        self.playing = playing
        if playing and self.tick is None:
            self.tick = GLib.timeout_add(50, self._step)     # 20 fps: smooth, light on battery
        elif not playing and self.tick is not None:
            GLib.source_remove(self.tick)
            self.tick = None
            for bar in self.bars:
                bar.set_size_request(3, 3)

    def _step(self):
        t = time.monotonic()
        for i, (bar, speed) in enumerate(zip(self.bars, (7.0, 5.2, 8.4, 6.1))):
            level = 0.25 + 0.75 * abs(math.sin(t * speed + i * 1.7))
            bar.set_size_request(3, max(3, int(self.HEIGHT * level)))
        return GLib.SOURCE_CONTINUE


class IslandWindow(Gtk.ApplicationWindow):
    """Compact pill (clock, music, timer, news) that grows into a card on hover."""

    def __init__(self, app, layer_shell=None, place="bar"):
        super().__init__(application=app, title="Lennox island")
        self.app = app
        self.ls = layer_shell
        self.place = place
        self.state = {"ringing": [], "event": None, "call_since": None, "next_up": None, "music": None,
                      "stopwatch_running": False, "stopwatch_elapsed": 0, "show_music": True,
                      "fullscreen": False, "place": place, "h24": True}
        self.kind = None
        self.shown = None
        self.hovering = False
        self.pinned = False
        self._hover_source = 0
        self.music_seen = None          # (time, position) for a smooth progress bar
        self.add_css_class("lennox-island-window")
        self.set_decorated(False)
        self.set_resizable(False)

        top, height = bar_geometry() if place == "bar" else (6, 34)
        self.compact_height = max(26, height - 4)
        if self.ls:
            self.ls.init_for_window(self)
            self.ls.set_namespace(self, "lennox-island")
            self.ls.set_anchor(self, self.ls.Edge.TOP, True)
            self.ls.set_keyboard_mode(self, self.ls.KeyboardMode.NONE)
            if place == "bar":
                # Over the bar's middle, like the iPhone's island
                self.ls.set_layer(self, self.ls.Layer.OVERLAY)
                self.ls.set_exclusive_zone(self, -1)
                self.ls.set_margin(self, self.ls.Edge.TOP, top + 2)
            else:
                self.ls.set_layer(self, self.ls.Layer.TOP)
                self.ls.set_margin(self, self.ls.Edge.TOP, 6)

        self.pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["lennox-island"],
                            halign=Gtk.Align.CENTER)
        # Compact row
        self.compact = Gtk.Box(spacing=10, css_classes=["island-compact"])
        self.compact.set_size_request(-1, self.compact_height)
        self.art = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, css_classes=["island-art"],
                               valign=Gtk.Align.CENTER)
        self.art.set_size_request(22, 22)
        self.icon = Gtk.Image(pixel_size=16, valign=Gtk.Align.CENTER)
        self.label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END, max_width_chars=30, hexpand=True,
                               xalign=0, css_classes=["island-text"])
        self.detail = Gtk.Label(css_classes=["island-detail"])
        self.bars = EqBars()
        for w in (self.art, self.icon, self.label, self.detail, self.bars):
            self.compact.append(w)
        self.pill.append(self.compact)
        # Expanded card
        self.reveal = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                   transition_duration=260)
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, css_classes=["island-card"])
        self.reveal.set_child(self.card)
        self.pill.append(self.reveal)
        self.set_child(self.pill)

        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._hover(True))
        hover.connect("leave", lambda *_: self._hover(False))
        self.pill.add_controller(hover)
        click = Gtk.GestureClick()
        click.connect("released", self._clicked)
        self.compact.add_controller(click)

    # ---------------------------------------------------------------- state

    def set_clock(self, d, now):
        self.state["ringing"] = d["ringing"]
        self.state["next_up"] = C.next_up(d, now)
        sw = d["stopwatch"]
        self.state["stopwatch_running"] = sw["start"] is not None
        self.state["stopwatch_elapsed"] = C.stopwatch_elapsed(sw, now)

    def set_status(self, status):
        music = status.get("music")
        old = self.state.get("music")
        if music and music.get("position") is not None:
            self.music_seen = (time.time(), music["position"])
        elif not music or (old and old.get("title") != music.get("title")):
            self.music_seen = None
        self.state["music"] = music
        self.state["fullscreen"] = bool(status.get("fullscreen"))
        if status.get("call") and not self.state["call_since"]:
            self.state["call_since"] = time.time()
        elif not status.get("call"):
            self.state["call_since"] = None

    def event(self, icon, text, seconds=EVENT_SECONDS):
        self.state["event"] = {"icon": icon, "text": text, "until": time.time() + seconds}
        self.render()

    # ---------------------------------------------------------------- drawing

    def _button(self, icon, tooltip, callback, css=None):
        b = Gtk.Button(icon_name=icon, tooltip_text=tooltip, css_classes=["island-button"] + (css or []),
                       valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: callback())
        return b

    def _clear_card(self):
        child = self.card.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.card.remove(child)
            child = nxt

    def _clock_text(self, now):
        local = time.localtime(now)
        return time.strftime("%H:%M" if self.state.get("h24", True) else "%-I:%M %p", local)

    def render(self, now=None):
        now = now or time.time()
        chosen = choose(self.state, now)
        if chosen is None:
            self.kind = None
            self.reveal.set_reveal_child(False)
            self.set_visible(False)
            return
        kind, info = chosen
        if self.ls and self.place != "bar":
            self.ls.set_layer(self, self.ls.Layer.OVERLAY if kind == "ringing" else self.ls.Layer.TOP)
        for cls in ("ringing", "event", "call", "timer", "music", "stopwatch", "clock", "expanded"):
            self.pill.remove_css_class(cls)
        self.pill.add_css_class(kind)
        key = (kind, show_key(kind, info))
        rebuild = key != self.shown
        self.shown = key
        self.kind = kind
        getattr(self, f"_show_{kind}")(info, now, rebuild)
        expanded = kind == "ringing" or ((self.hovering or self.pinned) and kind in ("music", "timer", "clock"))
        if expanded:
            self.pill.add_css_class("expanded")
        self.reveal.set_reveal_child(expanded)
        self.set_visible(True)

    def _compact(self, icon=None, text="", detail="", art=None, bars=False):
        self.art.set_visible(bool(art))
        if art:
            self.art.set_filename(art)
        self.icon.set_visible(bool(icon) and not art)
        if icon:
            self.icon.set_from_icon_name(icon)
        self.label.set_label(text)
        self.label.set_visible(bool(text))
        self.detail.set_label(detail)
        self.detail.set_visible(bool(detail))
        self.bars.set_visible(bars)

    def _show_clock(self, _info, now, rebuild):
        up = self.state.get("next_up")
        hint = ""
        if up and up[0] == "alarm":
            hint = f"󰀠 {up[1]['time']}"
        self._compact(text=self._clock_text(now), detail=hint)
        self.label.set_xalign(0.5)
        self.bars.set_playing(False)
        if rebuild:
            self._clear_card()
            date = Gtk.Label(label=time.strftime("%A %-d %B", time.localtime(now)), css_classes=["island-title"])
            self.card.append(date)
            self.card_next = Gtk.Label(css_classes=["island-sub"], wrap=True, justify=Gtk.Justification.CENTER)
            self.card.append(self.card_next)
            row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
            for label, tab in (("Timer", "timers"), ("Alarm", "alarms"), ("Stopwatch", "stopwatch")):
                b = Gtk.Button(label=label, css_classes=["island-pill-button"])
                b.connect("clicked", lambda _b, t=tab: self._open_clock(t))
                row.append(b)
            self.card.append(row)
        if up:
            kind, item, left = up
            what = item.get("label") or item.get("text") or kind
            self.card_next.set_label(f"Next: {what} in {C.short_left(left)}")
        else:
            self.card_next.set_label("No timers or alarms")

    def _show_music(self, info, now, rebuild):
        artist = info.get("artist") or ""
        art = info.get("art_file")
        self._compact(icon=None if art else "audio-x-generic-symbolic", text=info["title"], art=art, bars=True)
        self.label.set_xalign(0)
        self.bars.set_playing(True)
        if rebuild:
            self._clear_card()
            top = Gtk.Box(spacing=12)
            cover = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, css_classes=["island-cover"])
            cover.set_size_request(64, 64)
            if art:
                cover.set_filename(art)
            top.append(cover)
            words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
            words.append(Gtk.Label(label=info["title"], xalign=0, css_classes=["island-title"],
                                   ellipsize=Pango.EllipsizeMode.END, max_width_chars=26))
            words.append(Gtk.Label(label=artist, xalign=0, css_classes=["island-sub"],
                                   ellipsize=Pango.EllipsizeMode.END, max_width_chars=30))
            top.append(words)
            self.card.append(top)
            self.progress_row = Gtk.Box(spacing=8)
            self.pos_label = Gtk.Label(css_classes=["island-time"])
            self.progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER, css_classes=["island-progress"])
            self.len_label = Gtk.Label(css_classes=["island-time"])
            for w in (self.pos_label, self.progress, self.len_label):
                self.progress_row.append(w)
            self.card.append(self.progress_row)
            controls = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
            player = info["player"]
            controls.append(self._button("media-skip-backward-symbolic", "Previous",
                                         lambda: self.app.mpris.command(player, "Previous")))
            controls.append(self._button("media-playback-pause-symbolic", "Pause",
                                         lambda: self.app.mpris.command(player, "PlayPause"), ["big"]))
            controls.append(self._button("media-skip-forward-symbolic", "Next",
                                         lambda: self.app.mpris.command(player, "Next")))
            self.card.append(controls)
        length = info.get("length")
        if length and self.music_seen:
            seen_at, pos = self.music_seen
            pos = min(length, pos + (now - seen_at))
            self.progress.set_fraction(pos / length)
            self.pos_label.set_label(C.countdown(pos))
            self.len_label.set_label(C.countdown(length))
            self.progress_row.set_visible(True)
        else:
            self.progress_row.set_visible(False)

    def _show_timer(self, info, now, rebuild):
        item = info["item"]
        icon = {"timer": "timer-symbolic", "alarm": "alarm-symbolic", "reminder": "appointment-soon-symbolic"}
        paused = info["kind"] == "timer" and item.get("paused_left") is not None
        left = C.countdown(info["left"]) + (" ⏸" if paused else "")
        self._compact(icon=icon[info["kind"]], text=item.get("label") or item.get("text") or "", detail=left)
        self.label.set_xalign(0)
        self.bars.set_playing(False)
        if rebuild:
            self._clear_card()
            self.big = Gtk.Label(css_classes=["island-big"])
            self.card.append(self.big)
            if info["kind"] == "timer":
                row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
                row.append(self._button("media-playback-start-symbolic" if paused else "media-playback-pause-symbolic",
                                        "Resume" if paused else "Pause",
                                        lambda i=item["id"]: self._clock(lambda d, n: C.pause_timer(d, i, n))))
                row.append(self._button("window-close-symbolic", "Cancel",
                                        lambda i=item["id"]: self._clock(lambda d, n: C.cancel(d, i))))
                self.card.append(row)
        self.big.set_label(left)

    def _show_ringing(self, info, now, rebuild):
        self._compact(icon="alarm-symbolic", text=info["label"])
        self.label.set_xalign(0)
        self.bars.set_playing(False)
        if rebuild:
            self._clear_card()
            row = Gtk.Box(spacing=10, homogeneous=True)
            snooze = Gtk.Button(label="Snooze 10 min", css_classes=["island-pill-button"])
            snooze.connect("clicked", lambda _b: self._clock(lambda d, n: C.snooze(d, n)))
            stop = Gtk.Button(label="Stop", css_classes=["island-pill-button", "stop"])
            stop.connect("clicked", lambda _b: self._clock(lambda d, n: C.stop_ringing(d)))
            row.append(snooze)
            row.append(stop)
            self.card.append(row)

    def _show_event(self, info, now, rebuild):
        self._compact(icon=info["icon"], text=info["text"])
        self.label.set_xalign(0)
        self.bars.set_playing(False)

    def _show_call(self, info, now, rebuild):
        self._compact(icon="audio-input-microphone-symbolic", text="On a call", detail=C.countdown(now - info["since"]))
        self.label.set_xalign(0)
        self.bars.set_playing(False)

    def _show_stopwatch(self, info, now, rebuild):
        self._compact(icon="stopwatch-symbolic", text="Stopwatch", detail=C.countdown(info["elapsed"]))
        self.label.set_xalign(0)
        self.bars.set_playing(False)

    # ---------------------------------------------------------------- input

    def _hover(self, inside):
        if self._hover_source:
            GLib.source_remove(self._hover_source)
        # Open a moment after the pointer arrives, close a little after it leaves
        self._hover_source = GLib.timeout_add(150 if inside else 450, self._apply_hover, inside)

    def _apply_hover(self, inside):
        self._hover_source = 0
        self.hovering = inside
        if not inside:
            self.pinned = False
        self.render()
        return GLib.SOURCE_REMOVE

    def _clicked(self, *_args):
        if self.kind in ("music", "timer", "clock"):
            self.pinned = not self.pinned
            self.render()
        elif self.kind == "stopwatch":
            self._open_clock("stopwatch")

    def _open_clock(self, tab):
        try:
            subprocess.Popen([os.path.expanduser("~/.local/bin/lennox-clock"), tab], start_new_session=True)
        except OSError:
            pass

    def _clock(self, change):
        with C.edit() as d:
            change(d, time.time())
        self.app.clock_tick()
