"""What's playing: talks to music players over D-Bus (MPRIS).

Spotify, browsers (YouTube), mpv, Vesktop... all show up here. The
player that is playing wins; otherwise the last one that played.
"""

from gi.repository import Gio, GLib

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
TIMEOUT_MS = 400


class Mpris:
    def __init__(self, bus=None):
        self._bus = bus
        self._last = None

    @property
    def bus(self):
        if self._bus is None:
            try:
                self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            except GLib.Error:
                return None
        return self._bus

    def _call(self, dest, path, iface, method, args=None, reply="()"):
        bus = self.bus
        if bus is None:
            return None
        try:
            result = bus.call_sync(dest, path, iface, method, args,
                                   GLib.VariantType(reply) if reply else None,
                                   Gio.DBusCallFlags.NONE, TIMEOUT_MS, None)
        except GLib.Error:
            return None
        return result.unpack() if result is not None else None

    def players(self):
        names = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                           "ListNames", reply="(as)")
        if not names:
            return []
        return sorted(n for n in names[0] if n.startswith(PREFIX))

    def _props(self, name):
        props = self._call(name, PATH, "org.freedesktop.DBus.Properties", "GetAll",
                           GLib.Variant("(s)", (PLAYER,)), reply="(a{sv})")
        return props[0] if props else None

    def now_playing(self):
        """A dict for the playing (or last) player, or None if there is none."""
        found = []
        for name in self.players():
            props = self._props(name)
            if props is None:
                continue
            meta = props.get("Metadata") or {}
            title = str(meta.get("xesam:title") or "").strip()
            if not title:
                continue
            artist = meta.get("xesam:artist") or []
            if isinstance(artist, str):
                artist = [artist]
            found.append({
                "player": name,
                "title": title,
                "artist": ", ".join(str(a) for a in artist if a),
                "album": str(meta.get("xesam:album") or ""),
                "art": str(meta.get("mpris:artUrl") or ""),
                "playing": props.get("PlaybackStatus") == "Playing",
                "can_next": bool(props.get("CanGoNext", True)),
                "can_prev": bool(props.get("CanGoPrevious", True)),
                # Seconds, or None when the player doesn't say (the island hides the progress bar)
                "length": (meta.get("mpris:length") or 0) / 1e6 or None,
                "position": props["Position"] / 1e6 if isinstance(props.get("Position"), int) else None,
            })
        if not found:
            self._last = None
            return None
        for info in found:
            if info["playing"]:
                self._last = info["player"]
                return info
        for info in found:
            if info["player"] == self._last:
                return info
        return found[0]

    def command(self, player, method):
        """method: PlayPause, Next or Previous."""
        if method in ("PlayPause", "Next", "Previous"):
            self._call(player, PATH, PLAYER, method, reply=None)
