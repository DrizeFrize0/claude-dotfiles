"""A fake MPRIS music player on the session bus, logging commands to $MPRIS_LOG."""
import os
import sys

from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="PlayPause"/><method name="Next"/><method name="Previous"/>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="Position" type="x" access="read"/>
  </interface>
</node>"""
LOG = os.environ.get("MPRIS_LOG", "/dev/null")
ART = sys.argv[1] if len(sys.argv) > 1 else ""
state = {"status": "Playing", "track": 0}
TRACKS = [("Blinding Lights", ["The Weeknd"]), ("Starboy", ["The Weeknd", "Daft Punk"])]


def meta():
    title, artist = TRACKS[state["track"] % 2]
    d = {"mpris:length": GLib.Variant("x", 200_000_000), "xesam:title": GLib.Variant("s", title), "xesam:artist": GLib.Variant("as", artist),
         "xesam:album": GLib.Variant("s", "After Hours"), "mpris:trackid": GLib.Variant("o", "/t/1")}
    if ART:
        d["mpris:artUrl"] = GLib.Variant("s", "file://" + ART)
    return d


def on_call(conn, sender, path, iface, method, params, inv):
    with open(LOG, "a") as f:
        f.write(method + "\n")
    if method == "PlayPause":
        state["status"] = "Paused" if state["status"] == "Playing" else "Playing"
    elif method == "Next":
        state["track"] += 1
    elif method == "Previous":
        state["track"] -= 1
    inv.return_value(None)


def on_get(conn, sender, path, iface, prop):
    return {"Position": GLib.Variant("x", 73_000_000), "PlaybackStatus": GLib.Variant("s", state["status"]),
            "Metadata": GLib.Variant("a{sv}", meta()),
            "CanGoNext": GLib.Variant("b", True),
            "CanGoPrevious": GLib.Variant("b", False)}[prop]


def on_bus(conn, name):
    info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
    conn.register_object("/org/mpris/MediaPlayer2", info, on_call, on_get, None)


Gio.bus_own_name(Gio.BusType.SESSION, "org.mpris.MediaPlayer2.fakeplayer", Gio.BusNameOwnerFlags.NONE,
                 on_bus, None, None)
GLib.MainLoop().run()
