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
        self.mpris = mpris
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

    def _poll(self, first):
        music = self.mpris.now_playing() if self.mpris else None
        if music and music.get("art"):
            music["art_file"] = data.art_file(music["art"])
        status = {"music": music, "call": mic_in_use(), "ac": on_ac(), "wifi": wifi_name(),
                  "bt": bluetooth_devices(), "dnd": dnd_on()}
        events = [] if first else self._changes(status)
        self.last = status
        GLib.idle_add(self._deliver, status, events)

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
                GLib.idle_add(self.on_notification, app, summary, urgency)
        except Exception:  # noqa: BLE001
            pass
        return None  # monitors only watch


# ---------------------------------------------------------------- the window

class IslandWindow(Gtk.ApplicationWindow):
    def __init__(self, app, layer_shell=None):
        super().__init__(application=app, title="Lennox island")
        self.app = app
        self.ls = layer_shell
        self.state = {"ringing": [], "event": None, "call_since": None, "next_up": None, "music": None,
                      "stopwatch_running": False, "stopwatch_elapsed": 0, "show_music": True}
        self.add_css_class("lennox-island-window")
        self.set_decorated(False)
        self.set_resizable(False)
        if self.ls:
            self.ls.init_for_window(self)
            self.ls.set_namespace(self, "lennox-island")
            self.ls.set_layer(self, self.ls.Layer.TOP)
            self.ls.set_anchor(self, self.ls.Edge.TOP, True)
            self.ls.set_margin(self, self.ls.Edge.TOP, 6)
            self.ls.set_keyboard_mode(self, self.ls.KeyboardMode.NONE)

        self.pill = Gtk.Box(spacing=10, css_classes=["lennox-island"])
        self.icon = Gtk.Image(pixel_size=18)
        self.art = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, css_classes=["island-art"])
        self.art.set_size_request(26, 26)
        self.label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END, max_width_chars=42, css_classes=["island-text"])
        self.detail = Gtk.Label(css_classes=["island-detail"])
        self.buttons = Gtk.Box(spacing=4)
        self.extra = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT, transition_duration=220)
        self.extra.set_child(self.buttons)
        for w in (self.art, self.icon, self.label, self.detail, self.extra):
            self.pill.append(w)
        self.set_child(self.pill)

        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._hover(True))
        hover.connect("leave", lambda *_: self._hover(False))
        self.pill.add_controller(hover)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self._clicked())
        self.pill.add_controller(click)
        self.hovering = False
        self.kind = None
        self.shown = None

    # -- state from outside
    def set_clock(self, d, now):
        self.state["ringing"] = d["ringing"]
        self.state["next_up"] = C.next_up(d, now)
        sw = d["stopwatch"]
        self.state["stopwatch_running"] = sw["start"] is not None
        self.state["stopwatch_elapsed"] = C.stopwatch_elapsed(sw, now)

    def set_status(self, status):
        self.state["music"] = status.get("music")
        if status.get("call") and not self.state["call_since"]:
            self.state["call_since"] = time.time()
        elif not status.get("call"):
            self.state["call_since"] = None

    def event(self, icon, text, seconds=EVENT_SECONDS):
        self.state["event"] = {"icon": icon, "text": text, "until": time.time() + seconds}
        self.render()

    # -- drawing
    def _button(self, icon, tooltip, callback, css=None):
        b = Gtk.Button(icon_name=icon, tooltip_text=tooltip, css_classes=["island-button"] + (css or []))
        b.connect("clicked", lambda _b: callback())
        return b

    def render(self, now=None):
        now = now or time.time()
        chosen = choose(self.state, now)
        if chosen is None:
            self.kind = None
            self.set_visible(False)
            return
        kind, info = chosen
        if self.ls:
            # Ringing shows over fullscreen games and videos, the rest stays out of the way
            self.ls.set_layer(self, self.ls.Layer.OVERLAY if kind == "ringing" else self.ls.Layer.TOP)
        for cls in ("ringing", "event", "call", "timer", "music", "stopwatch"):
            self.pill.remove_css_class(cls)
        self.pill.add_css_class(kind)
        self.art.set_visible(False)
        self.icon.set_visible(True)
        self.detail.set_label("")
        key = (kind, show_key(kind, info))
        rebuild = key != self.shown
        self.shown = key

        if kind == "ringing":
            self.icon.set_from_icon_name("alarm-symbolic")
            self.label.set_label(info["label"])
            if rebuild:
                self._set_buttons([self._button("alarm-symbolic", "Snooze 10 minutes", self._snooze),
                                   self._button("process-stop-symbolic", "Stop", self._stop, ["destructive"])])
            self.extra.set_reveal_child(True)
        elif kind == "event":
            self.icon.set_from_icon_name(info["icon"])
            self.label.set_label(info["text"])
            self.extra.set_reveal_child(False)
        elif kind == "call":
            self.icon.set_from_icon_name("audio-input-microphone-symbolic")
            self.label.set_label("On a call")
            self.detail.set_label(C.countdown(now - info["since"]))
            self.extra.set_reveal_child(False)
        elif kind == "timer":
            item = info["item"]
            self.icon.set_from_icon_name({"timer": "timer-symbolic", "alarm": "alarm-symbolic",
                                          "reminder": "appointment-soon-symbolic"}[info["kind"]])
            self.label.set_label(item.get("label") or item.get("text") or "")
            paused = info["kind"] == "timer" and item.get("paused_left") is not None
            self.detail.set_label(C.countdown(info["left"]) + (" ⏸" if paused else ""))
            if rebuild and info["kind"] == "timer":
                self._set_buttons([self._button("media-playback-start-symbolic" if paused
                                                else "media-playback-pause-symbolic", "Pause / resume",
                                                lambda i=item["id"]: self._clock(lambda d, n: C.pause_timer(d, i, n))),
                                   self._button("window-close-symbolic", "Cancel",
                                                lambda i=item["id"]: self._clock(lambda d, n: C.cancel(d, i)))])
            self.extra.set_reveal_child(self.hovering and info["kind"] == "timer")
        elif kind == "stopwatch":
            self.icon.set_from_icon_name("stopwatch-symbolic")
            self.label.set_label("Stopwatch")
            self.detail.set_label(C.countdown(info["elapsed"]))
            self.extra.set_reveal_child(False)
        elif kind == "music":
            art = info.get("art_file")
            if art:
                self.art.set_filename(art)
                self.art.set_visible(True)
                self.icon.set_visible(False)
            else:
                self.icon.set_from_icon_name("audio-x-generic-symbolic")
            artist = f" · {info['artist']}" if info.get("artist") else ""
            self.label.set_label(info["title"] + artist)
            if rebuild:
                player = info["player"]
                self._set_buttons([self._button("media-skip-backward-symbolic", "Previous",
                                                lambda: self.app.mpris.command(player, "Previous")),
                                   self._button("media-playback-pause-symbolic", "Pause",
                                                lambda: self.app.mpris.command(player, "PlayPause")),
                                   self._button("media-skip-forward-symbolic", "Next",
                                                lambda: self.app.mpris.command(player, "Next"))])
            self.extra.set_reveal_child(self.hovering)
        self.kind = kind
        self.set_visible(True)

    def _set_buttons(self, buttons):
        child = self.buttons.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.buttons.remove(child)
            child = nxt
        for b in buttons:
            self.buttons.append(b)

    def _hover(self, inside):
        self.hovering = inside
        if self.kind in ("music", "timer"):
            self.extra.set_reveal_child(inside)

    def _clicked(self):
        if self.kind in ("timer", "stopwatch", "ringing"):
            try:
                subprocess.Popen([os.path.expanduser("~/.local/bin/lennox-clock"),
                                  "stopwatch" if self.kind == "stopwatch" else "timers"],
                                 start_new_session=True)
            except OSError:
                pass

    def _clock(self, change):
        with C.edit() as d:
            change(d, time.time())
        self.app.clock_tick()

    def _snooze(self):
        self._clock(lambda d, n: C.snooze(d, n))

    def _stop(self):
        self._clock(lambda d, n: C.stop_ringing(d))
