"""The dynamic island: a pill under the bar that grows to show what's happening.

It springs between sizes and cross-fades between activities; an idle island
runs no timers. Icons: the bundled set in ~/.config/lennox/assets/icons/island.

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
import functools
import glob
import json
import math
import os
import subprocess
import threading
import time

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Graphene, Gsk, Gtk, Pango  # noqa: E402

from .. import clock as C  # noqa: E402
from .. import sounds  # noqa: E402
from . import data  # noqa: E402
from .cards import scaled_texture  # noqa: E402

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
    focus = state.get("focus")
    if focus and focus.get("active"):
        return "focus", focus
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
    if kind == "focus":
        return info.get("phase"), info.get("round")
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
        self.slow = {}
        self.rounds = 0
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    SLOW_EVERY = 3

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
        # Every 2 s: what changes fast (music over D-Bus, power in sysfs, fullscreen). The
        # programs that cost a process each (mic, Wi-Fi, Bluetooth, Do not disturb) every
        # 3rd round, in between the last answer stands: ~3x fewer wake-ups on battery
        self.rounds += 1
        if first or self.rounds % self.SLOW_EVERY == 0:
            self.slow = {"call": mic_in_use(), "wifi": wifi_name(), "bt": bluetooth_devices(), "dnd": dnd_on()}
        status = {"music": music, "ac": on_ac(), "fullscreen": fullscreen_active(), **self.slow}
        events = [] if first else self._changes(status)
        self.last = status
        GLib.idle_add(self._deliver, status, events, priority=GLib.PRIORITY_DEFAULT)

    def _changes(self, s):
        events, old = [], self.last
        if s["ac"] is not None and old.get("ac") is not None and s["ac"] != old["ac"]:
            bat = data.battery()
            level = f" · {bat[0]}%" if bat else ""
            events.append(("battery-full-charging-symbolic", "Charging" + level, "plug") if s["ac"]
                          else ("battery-good-symbolic", "On battery" + level, "unplug"))
        if s["wifi"] is not None and old.get("wifi") is not None and s["wifi"] != old["wifi"]:
            events.append(("network-wireless-symbolic", f"Connected to {s['wifi']}", None) if s["wifi"]
                          else ("network-wireless-offline-symbolic", "Wi-Fi disconnected", None))
        if s["bt"] is not None and old.get("bt") is not None:
            for name in sorted(s["bt"] - old["bt"]):
                events.append(("bluetooth-active-symbolic", f"{name} connected", "connect"))
            for name in sorted(old["bt"] - s["bt"]):
                events.append(("bluetooth-disabled-symbolic", f"{name} disconnected", "disconnect"))
        return events

    def _deliver(self, status, events):
        self.on_update(status)
        for icon, text, sound in events:
            self.on_event(icon, text)
            if sound:
                sounds.play(sound)
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


# ---------------------------------------------------------------- icons

ICON_DIR = os.path.expanduser("~/.config/lennox/assets/icons/island")
# Icon names the rest of Lennox sends (lennox-osd, lennox-clips, notifications,
# focus) -> the bundled island set (Phosphor, MIT: see LICENSE next to them)
ICON_ALIASES = {
    "audio-volume-high": "volume", "audio-volume-medium": "volume", "audio-volume-low": "volume",
    "audio-volume-muted": "volume-off", "audio-input-microphone": "mic", "microphone-sensitivity-muted": "mic-off",
    "display-brightness": "brightness", "keyboard-brightness": "brightness", "media-record": "record",
    "battery-full-charging": "charging", "battery-good": "battery", "battery-low": "battery-low",
    "network-wireless": "wifi", "network-wireless-offline": "wifi-off",
    "bluetooth-active": "bluetooth", "bluetooth-disabled": "bluetooth-off",
    "mail-unread": "notification", "dialog-warning": "panic", "appointment-soon": "reminder",
    "audio-x-generic": "music", "find-location": "focus", "face-smile": "break",
    "media-playback-start": "play", "media-playback-pause": "pause", "media-skip-backward": "skip-back",
    "media-skip-forward": "skip-forward", "window-close": "close", "object-select": "check",
    "power-profile-power-saver": "battery", "power-profile-balanced": "performance",
    "power-profile-performance": "performance", "input-gaming": "game", "camera-photo": "camera",
    "system-lock-screen": "lock", "call-start": "call",
}
# Which glow ring an event gets, by its icon (the rest: the theme accent)
ICON_GLOW = {"record": "red", "panic": "red", "mic": "blue", "mic-off": "blue", "call": "blue",
             "charging": "green", "plug": "green", "check": "green", "focus": "green", "break": "green",
             "alarm": "amber", "timer": "amber", "reminder": "amber", "stopwatch": "amber"}
KIND_GLOW = {"music": "accent", "timer": "amber", "stopwatch": "amber", "ringing": "amber",
             "focus": "green", "call": "blue"}
KINDS = ("ringing", "event", "call", "focus", "timer", "stopwatch", "music", "clock")
GLOWS = ("glow-accent", "glow-amber", "glow-green", "glow-red", "glow-blue")


def icon_key(name):
    """'alarm-symbolic' / 'alarm' / 'audio-volume-high-symbolic' -> the island set's name for it."""
    base = (name or "").removesuffix("-symbolic")
    return ICON_ALIASES.get(base, base)


@functools.lru_cache(maxsize=128)
def island_icon(name):
    """The bundled icon for this name, as a Gio.FileIcon (a "-symbolic.svg" file, so
    GTK recolors it like theme icons), or the name itself when the set lacks it."""
    path = os.path.join(ICON_DIR, f"island-{icon_key(name)}-symbolic.svg")
    if name and os.path.exists(path):
        return Gio.FileIcon.new(Gio.File.new_for_path(path))
    return name


def set_icon(image, name):
    """Show an icon in a Gtk.Image (only when it changed)."""
    if getattr(image, "lennox_icon", None) == name:
        return
    image.lennox_icon = name
    icon = island_icon(name)
    if isinstance(icon, Gio.Icon):
        image.set_from_gicon(icon)
    else:
        image.set_from_icon_name(icon)


def glow_for(kind, info):
    if kind == "event":
        return ICON_GLOW.get(icon_key(info.get("icon")), "accent")
    return KIND_GLOW.get(kind)


# ---------------------------------------------------------------- the window

SPRING = (0.8, 1.0, 320.0)      # damping, mass, stiffness: quick, a touch of overshoot
BOUNCE = (0.45, 1.0, 420.0)     # a new event: a small wobble


class SpringBin(Gtk.Widget):
    """The black pill. Its size springs toward its content's size (Adw.SpringAnimation)
    instead of jumping; meanwhile the content is laid out at its final size and
    clipped. The animation runs on the frame clock only while it moves, so an idle
    island has no timers at all."""

    def __init__(self, child, **kwargs):
        super().__init__(overflow=Gtk.Overflow.HIDDEN, **kwargs)
        self.child = child
        child.set_parent(self)
        self.size = None            # (w, h) while springing; None = exactly the content's size
        self.start = self.goal = None
        self.anim = None

    def do_dispose(self):
        if self.child is not None:
            self.child.unparent()
            self.child = None
        super().do_dispose()

    def content_size(self):
        width = self.child.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
        return width, self.child.measure(Gtk.Orientation.VERTICAL, width)[1]

    def moving(self):
        return self.anim is not None and self.anim.get_state() == Adw.AnimationState.PLAYING

    def resize(self, bounce=False):
        """Spring from the size shown now to the content's size."""
        goal = self.content_size()
        if not self.get_mapped() or self.get_width() <= 0:
            self.stop()
            return
        shown = self.size if self.size is not None else (self.get_width(), self.get_height())
        if not bounce and goal == (self.goal if self.moving() else shown):
            return
        if bounce:
            shown = (max(goal[0] * 0.86, goal[0] - 28), shown[1])
        self.start, self.goal = shown, goal
        if self.anim is None:
            self.anim = Adw.SpringAnimation.new(self, 0.0, 1.0, Adw.SpringParams.new(*SPRING),
                                                Adw.CallbackAnimationTarget.new(self._step))
            self.anim.set_clamp(False)
            self.anim.set_epsilon(0.004)      # within ~half a pixel: done (no long invisible tail)
            self.anim.connect("done", self._done)
        self.anim.set_spring_params(Adw.SpringParams.new(*(BOUNCE if bounce else SPRING)))
        self.anim.play()

    def stop(self):
        if self.moving():
            self.anim.skip()
        self.size = None

    def _step(self, value):
        (sw, sh), (gw, gh) = self.start, self.goal
        height = min(max(sh + (gh - sh) * value, min(sh, gh)), max(sh, gh))   # only the width overshoots
        self.size = (max(1.0, sw + (gw - sw) * value), height)
        self.queue_resize()

    def _done(self, *_args):
        self.size = None
        self.queue_resize()

    def do_measure(self, orientation, for_size):
        if self.size is not None:
            value = max(1, int(round(self.size[0 if orientation == Gtk.Orientation.HORIZONTAL else 1])))
            return value, value, -1, -1
        return self.child.measure(orientation, for_size)

    def do_size_allocate(self, width, height, baseline):
        cw, ch = self.goal if self.size is not None else (width, height)
        cw = max(cw, self.child.measure(Gtk.Orientation.HORIZONTAL, -1)[0])
        ch = max(ch, self.child.measure(Gtk.Orientation.VERTICAL, cw)[0])
        point = Graphene.Point().init((width - cw) / 2, 0)      # centred, grows from the top
        self.child.allocate(cw, ch, -1, Gsk.Transform.new().translate(point))


class Ring(Gtk.Widget):
    """A circular countdown: a faint circle and the part that's left, in the CSS
    color. Redrawn only when the value changes (it has no timer of its own)."""

    def __init__(self, size, line=2.5):
        super().__init__(css_classes=["island-ring"], valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        self.px = size
        self.line = line
        self.fraction = 1.0

    def do_measure(self, orientation, for_size):
        return self.px, self.px, -1, -1

    def set_fraction(self, fraction):
        fraction = min(1.0, max(0.0, fraction))
        if abs(fraction - self.fraction) > 1e-3:
            self.fraction = fraction
            self.queue_draw()

    @staticmethod
    def _arc(cx, cy, r, fraction):
        b = Gsk.PathBuilder.new()
        if fraction >= 0.999:
            b.add_circle(Graphene.Point().init(cx, cy), r)
        else:
            a = -math.pi / 2 + 2 * math.pi * fraction
            b.move_to(cx, cy - r)
            b.svg_arc_to(r, r, 0, fraction > 0.5, True, cx + r * math.cos(a), cy + r * math.sin(a))
        return b.to_path()

    def do_snapshot(self, snapshot):
        w, h = self.get_width(), self.get_height()
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - self.line / 2 - 0.5
        color = self.get_color()
        faint = color.copy()
        faint.alpha *= 0.25
        stroke = Gsk.Stroke.new(self.line)
        stroke.set_line_cap(Gsk.LineCap.ROUND)
        snapshot.append_stroke(self._arc(cx, cy, r, 1.0), stroke, faint)
        if self.fraction > 0.005:
            snapshot.append_stroke(self._arc(cx, cy, r, self.fraction), stroke, color)


class EqBars(Gtk.Box):
    """Four little bars that dance while music plays (low and still when paused).
    Plain boxes whose height changes ~20 times a second: no cairo needed."""

    HEIGHT = 12

    def __init__(self):
        super().__init__(spacing=1, valign=Gtk.Align.CENTER, css_classes=["island-bars"])
        self.set_size_request(14, self.HEIGHT)
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


class Page:
    """One activity's look: its compact row and the card it grows into. Built once
    and then only updated; switching activity cross-fades to another page."""

    def __init__(self, win, kind, height, ring=False, art=False, bars=False):
        self.kind = kind
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["island-page", kind])
        self.compact = Gtk.Box(spacing=7, css_classes=["island-compact"])
        self.compact.set_size_request(-1, height)
        self.art_image = Gtk.Image(pixel_size=18)          # an Image is drawn exactly this big
        self.art = Gtk.Box(css_classes=["island-art"], valign=Gtk.Align.CENTER, overflow=Gtk.Overflow.HIDDEN,
                           visible=False)
        self.art.append(self.art_image)
        self.icon = Gtk.Image(pixel_size=11 if ring else 14, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        self.ring = Ring(22) if ring else None
        lead = self.icon
        if ring:
            lead = Gtk.Overlay(valign=Gtk.Align.CENTER)
            lead.set_child(self.ring)
            lead.add_overlay(self.icon)
        self.label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END, max_width_chars=18, hexpand=True,
                               xalign=0.5 if kind == "clock" else 0, css_classes=["island-text"])
        self.detail = Gtk.Label(css_classes=["island-detail"], visible=False)
        self.bars = EqBars() if bars else None
        for w in ((self.art,) if art else ()) + (lead, self.label, self.detail) + ((self.bars,) if bars else ()):
            self.compact.append(w)
        self.box.append(self.compact)
        self.reveal = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                   transition_duration=0)      # instant: the pill springs instead
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, css_classes=["island-card"])
        self.reveal.set_child(self.card)
        self.box.append(self.reveal)
        click = Gtk.GestureClick()
        click.connect("released", win._clicked)
        self.compact.add_controller(click)

    def set(self, icon=None, text="", detail="", art=None):
        texture = scaled_texture(art, 18) if art else None      # its pixel size is its shown size
        self.art.set_visible(texture is not None)
        if texture is not None and self.art_image.get_paintable() is not texture:
            self.art_image.set_from_paintable(texture)
        self.icon.set_visible(bool(icon) and texture is None)
        if icon:
            set_icon(self.icon, icon)
        if self.label.get_label() != text:
            self.label.set_label(text)
        self.label.set_visible(bool(text))
        if self.detail.get_label() != detail:
            self.detail.set_label(detail)
        self.detail.set_visible(bool(detail))


def big_ring(size=112):
    """The card's countdown: a big ring with the time inside."""
    ring = Ring(size, 4)
    label = Gtk.Label(css_classes=["island-big"], halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    box = Gtk.Overlay(halign=Gtk.Align.CENTER)
    box.set_child(ring)
    box.add_overlay(label)
    return box, ring, label


class IslandWindow(Gtk.ApplicationWindow):
    """Compact pill (clock, music, timer, news) that springs into a card on hover."""

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
        self.timer_id = None
        self.focus_phase = None
        self.add_css_class("lennox-island-window")
        self.set_decorated(False)
        self.set_resizable(False)

        top, height = bar_geometry() if place == "bar" else (6, 34)
        # In the bar: exactly the bar's height and position, so it covers the
        # bar's middle completely (nothing peeks out above or below)
        self.compact_height = max(26, height - 2)     # + the 1 px border = the bar's height
        self.top_margin = top
        if self.ls:
            self.ls.init_for_window(self)
            self.ls.set_namespace(self, "lennox-island")
            self.ls.set_anchor(self, self.ls.Edge.TOP, True)
            self.ls.set_keyboard_mode(self, self.ls.KeyboardMode.NONE)
            if place == "bar":
                # Over the bar's middle, like the iPhone's island
                self.ls.set_layer(self, self.ls.Layer.OVERLAY)
                self.ls.set_exclusive_zone(self, -1)
                self.ls.set_margin(self, self.ls.Edge.TOP, top)
            else:
                self.ls.set_layer(self, self.ls.Layer.TOP)
                self.ls.set_margin(self, self.ls.Edge.TOP, 6)

        # One page per activity in a cross-fading stack, inside the springing pill
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=220,
                               hhomogeneous=False, vhomogeneous=False)
        h = self.compact_height
        self.pages = {"clock": Page(self, "clock", h), "music": Page(self, "music", h, art=True, bars=True),
                      "timer": Page(self, "timer", h, ring=True), "focus": Page(self, "focus", h, ring=True),
                      "ringing": Page(self, "ringing", h), "event": Page(self, "event", h),
                      "call": Page(self, "call", h), "stopwatch": Page(self, "stopwatch", h)}
        for kind, page in self.pages.items():
            self.stack.add_named(page.box, kind)
            build = getattr(self, f"_build_{kind}", None)
            if build:
                build(page)
        self.pill = SpringBin(self.stack, css_classes=["lennox-island"], halign=Gtk.Align.CENTER)
        self.set_child(self.pill)

        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._hover(True))
        hover.connect("leave", lambda *_: self._hover(False))
        self.pill.add_controller(hover)

    # What the tests and older callers look at: the page on show
    @property
    def page(self):
        return self.pages[self.kind or "clock"]

    label = property(lambda self: self.page.label)
    detail = property(lambda self: self.page.detail)
    icon = property(lambda self: self.page.icon)
    art = property(lambda self: self.page.art)
    reveal = property(lambda self: self.page.reveal)
    bars = property(lambda self: self.pages["music"].bars)

    # ---------------------------------------------------------------- state

    def set_clock(self, d, now):
        self.state["ringing"] = d["ringing"]
        self.state["next_up"] = C.next_up(d, now)
        sw = d["stopwatch"]
        self.state["stopwatch_running"] = sw["start"] is not None
        self.state["stopwatch_elapsed"] = C.stopwatch_elapsed(sw, now)

    def set_focus(self, info):
        self.state["focus"] = info

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
        image = Gtk.Image()
        set_icon(image, icon)
        b = Gtk.Button(child=image, tooltip_text=tooltip, css_classes=["island-button"] + (css or []),
                       valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda _b: callback())
        return b

    def _clock_text(self, now):
        local = time.localtime(now)
        return time.strftime("%H:%M" if self.state.get("h24", True) else "%-I:%M %p", local)

    def render(self, now=None):
        now = now or time.time()
        chosen = choose(self.state, now)
        if chosen is None:
            self.kind = None
            for page in self.pages.values():
                page.reveal.set_reveal_child(False)
            self.bars.set_playing(False)
            self.set_visible(False)
            self.pill.stop()
            return
        kind, info = chosen
        if self.ls and self.place != "bar":
            self.ls.set_layer(self, self.ls.Layer.OVERLAY if kind == "ringing" else self.ls.Layer.TOP)
        for cls in KINDS + GLOWS + ("expanded",):
            self.pill.remove_css_class(cls)
        self.pill.add_css_class(kind)
        glow = glow_for(kind, info)
        if glow:
            self.pill.add_css_class(f"glow-{glow}")
        key = (kind, show_key(kind, info))
        new = key != self.shown
        self.shown = key
        self.kind = kind
        page = self.pages[kind]
        getattr(self, f"_show_{kind}")(info, now, page)
        if kind != "music":
            self.bars.set_playing(False)
        expanded = kind == "ringing" or ((self.hovering or self.pinned) and kind in ("music", "timer", "clock", "focus"))
        if expanded:
            self.pill.add_css_class("expanded")
        for other in self.pages.values():
            other.reveal.set_reveal_child(expanded and other is page)
            (other.box.add_css_class if expanded and other is page else other.box.remove_css_class)("expanded")
        if self.stack.get_visible_child_name() != kind:
            self.stack.set_visible_child_name(kind)
        self.set_visible(True)
        # A new event or alarm: a small bounce; anything else: spring to the new size
        self.pill.resize(bounce=new and kind in ("event", "ringing"))

    # clock -----------------------------------------------------------------

    def _build_clock(self, page):
        self.clock_date = Gtk.Label(css_classes=["island-title"])
        page.card.append(self.clock_date)
        self.card_next = Gtk.Label(css_classes=["island-sub"], wrap=True, justify=Gtk.Justification.CENTER)
        page.card.append(self.card_next)
        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        for label, tab in (("Timer", "timers"), ("Alarm", "alarms"), ("Stopwatch", "stopwatch")):
            b = Gtk.Button(label=label, css_classes=["island-pill-button"])
            b.connect("clicked", lambda _b, t=tab: self._open_clock(t))
            row.append(b)
        page.card.append(row)

    def _show_clock(self, _info, now, page):
        up = self.state.get("next_up")
        hint = f"󰀠 {up[1]['time']}" if up and up[0] == "alarm" else ""
        page.set(text=self._clock_text(now), detail=hint)
        self.clock_date.set_label(time.strftime("%A %-d %B", time.localtime(now)))
        if up:
            kind, item, left = up
            what = item.get("label") or item.get("text") or kind
            self.card_next.set_label(f"Next: {what} in {C.short_left(left)}")
        else:
            self.card_next.set_label("No timers or alarms")

    # music -----------------------------------------------------------------

    def _build_music(self, page):
        top = Gtk.Box(spacing=10)
        cover = Gtk.Box(css_classes=["island-cover"], valign=Gtk.Align.CENTER, overflow=Gtk.Overflow.HIDDEN)
        self.cover = Gtk.Image(pixel_size=44)
        cover.append(self.cover)
        top.append(cover)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        self.music_title = Gtk.Label(xalign=0, css_classes=["island-title"], ellipsize=Pango.EllipsizeMode.END,
                                     max_width_chars=22)
        self.music_artist = Gtk.Label(xalign=0, css_classes=["island-sub"], ellipsize=Pango.EllipsizeMode.END,
                                      max_width_chars=30)
        words.append(self.music_title)
        words.append(self.music_artist)
        top.append(words)
        page.card.append(top)
        self.progress_row = Gtk.Box(spacing=8)
        self.pos_label = Gtk.Label(css_classes=["island-time"])
        self.progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER, css_classes=["island-progress"])
        self.len_label = Gtk.Label(css_classes=["island-time"])
        for w in (self.pos_label, self.progress, self.len_label):
            self.progress_row.append(w)
        page.card.append(self.progress_row)
        controls = Gtk.Box(spacing=14, halign=Gtk.Align.CENTER)
        controls.append(self._button("media-skip-backward-symbolic", "Previous", lambda: self._player("Previous")))
        controls.append(self._button("media-playback-pause-symbolic", "Pause", lambda: self._player("PlayPause"),
                                     ["big"]))
        controls.append(self._button("media-skip-forward-symbolic", "Next", lambda: self._player("Next")))
        page.card.append(controls)
        self.cover_art = False

    def _player(self, command):
        music = self.state.get("music")
        if music and music.get("player"):
            self.app.mpris.command(music["player"], command)

    def _show_music(self, info, now, page):
        art = info.get("art_file")
        page.set(icon=None if art else "audio-x-generic-symbolic", text=info["title"], art=art)
        self.bars.set_playing(True)
        self.music_title.set_label(info["title"])
        self.music_artist.set_label(info.get("artist") or "")
        texture = scaled_texture(art, 44) if art else None
        if texture is not None:
            if self.cover.get_paintable() is not texture:
                self.cover.set_from_paintable(texture)
                self.cover.lennox_icon = None
        else:
            set_icon(self.cover, "audio-x-generic-symbolic")
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

    # timers ----------------------------------------------------------------

    def _build_timer(self, page):
        ring_box, self.timer_ring, self.timer_big = big_ring()
        page.card.append(ring_box)
        self.timer_buttons = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.timer_pause = self._button("media-playback-pause-symbolic", "Pause",
                                        lambda: self._clock(lambda d, n: C.pause_timer(d, self.timer_id, n)))
        self.timer_buttons.append(self.timer_pause)
        self.timer_buttons.append(self._button("window-close-symbolic", "Cancel",
                                               lambda: self._clock(lambda d, n: C.cancel(d, self.timer_id))))
        page.card.append(self.timer_buttons)

    def _show_timer(self, info, now, page):
        item, kind = info["item"], info["kind"]
        icon = {"timer": "timer-symbolic", "alarm": "alarm-symbolic", "reminder": "appointment-soon-symbolic"}
        paused = kind == "timer" and item.get("paused_left") is not None
        left = C.countdown(info["left"]) + (" ⏸" if paused else "")
        page.set(icon=icon[kind], text=item.get("label") or item.get("text") or "", detail=left)
        total = item.get("duration") if kind == "timer" else SOON
        fraction = info["left"] / total if total else 1.0
        page.ring.set_fraction(fraction)
        self.timer_ring.set_fraction(fraction)
        self.timer_big.set_label(left)
        self.timer_id = item.get("id")
        self.timer_buttons.set_visible(kind == "timer")
        set_icon(self.timer_pause.get_child(), "media-playback-start-symbolic" if paused
                 else "media-playback-pause-symbolic")
        self.timer_pause.set_tooltip_text("Resume" if paused else "Pause")

    # ringing ---------------------------------------------------------------

    def _build_ringing(self, page):
        row = Gtk.Box(spacing=10, homogeneous=True)
        snooze = Gtk.Button(label="Snooze 10 min", css_classes=["island-pill-button"])
        snooze.connect("clicked", lambda _b: self._clock(lambda d, n: C.snooze(d, n)))
        stop = Gtk.Button(label="Stop", css_classes=["island-pill-button", "stop"])
        stop.connect("clicked", lambda _b: self._clock(lambda d, n: C.stop_ringing(d)))
        row.append(snooze)
        row.append(stop)
        page.card.append(row)

    def _show_ringing(self, info, now, page):
        page.set(icon="alarm-symbolic", text=info["label"])

    # short ones ------------------------------------------------------------

    def _show_event(self, info, now, page):
        page.set(icon=info["icon"], text=info["text"])

    def _show_call(self, info, now, page):
        page.set(icon="audio-input-microphone-symbolic", text="On a call", detail=C.countdown(now - info["since"]))

    def _show_stopwatch(self, info, now, page):
        page.set(icon="stopwatch-symbolic", text="Stopwatch", detail=C.countdown(info["elapsed"]))

    # focus -----------------------------------------------------------------

    def _build_focus(self, page):
        ring_box, self.focus_ring, self.focus_big = big_ring()
        page.card.append(ring_box)
        self.focus_sub = Gtk.Label(css_classes=["island-sub"])
        page.card.append(self.focus_sub)
        row = Gtk.Box(spacing=10, homogeneous=True)
        more = Gtk.Button(label="+5 min", css_classes=["island-pill-button"])
        more.connect("clicked", lambda _b: self._focus("more", "5"))
        self.focus_stop = Gtk.Button(css_classes=["island-pill-button", "stop"])
        self.focus_stop.connect("clicked", lambda _b: self._focus("stop" if self.focus_phase == "focus" else "skip"))
        row.append(more)
        row.append(self.focus_stop)
        page.card.append(row)

    def _show_focus(self, info, now, page):
        focusing = info["phase"] == "focus"
        self.focus_phase = info["phase"]
        left = C.countdown(max(0, info["end"] - now))
        rounds = info.get("rounds", 1)
        name = "Focus" if focusing else "Break"
        if rounds > 1:
            name += f" {info.get('round', 1)}/{rounds}"
        page.set(icon="find-location-symbolic" if focusing else "face-smile-symbolic", text=name, detail=left)
        total = max(1.0, info["end"] - info.get("start", info["end"] - 1))
        fraction = max(0.0, info["end"] - now) / total
        page.ring.set_fraction(fraction)
        self.focus_ring.set_fraction(fraction)
        self.focus_big.set_label(left)
        self.focus_sub.set_label("Distractions are blocked, notifications wait" if focusing
                                 else "Stand up, stretch, drink some water")
        more_rounds = info.get("round", 1) < rounds
        self.focus_stop.set_label("Stop" if focusing else ("Next round now" if more_rounds else "Skip break"))

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
        if self.kind in ("music", "timer", "clock", "focus"):
            self.pinned = not self.pinned
            self.render()
        elif self.kind == "stopwatch":
            self._open_clock("stopwatch")

    def _focus(self, *args):
        try:
            subprocess.Popen([os.path.expanduser("~/.local/bin/lennox-focus"), *args], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _open_clock(self, tab):
        try:
            subprocess.Popen([os.path.expanduser("~/.local/bin/lennox-clock"), tab], start_new_session=True)
        except OSError:
            pass

    def _clock(self, change):
        with C.edit() as d:
            change(d, time.time())
        self.app.clock_tick()
