"""Sound: output and microphone, volumes, and a microphone test."""

import json

from gi.repository import Adw, Gtk

from .. import rows
from ..util import Debouncer, launch, lennox_bin, run_async

MIC_TEST = (
    'f="${XDG_RUNTIME_DIR:-/tmp}/lennox-mic-test.wav"; rm -f "$f"; '
    'timeout -s INT 4 pw-record --channels 1 "$f"; '
    'pw-play "$f"; rm -f "$f"'
)


def _percent(device):
    for channel in (device.get("volume") or {}).values():
        try:
            return int(str(channel.get("value_percent", "0")).rstrip("%"))
        except (ValueError, AttributeError):
            continue
    return 0


class DeviceSection:
    """Output or input: device picker, volume slider, mute switch."""

    def __init__(self, page, kind, title, description):
        self.page = page
        self.kind = kind                      # "sink" or "source"
        self.devices = []
        self.updating = False
        self.group = Adw.PreferencesGroup(title=title, description=description)

        self.combo = Adw.ComboRow(title="Device")
        self.combo.connect("notify::selected", self._on_device)
        self.group.add(self.combo)

        self.volume_debounce = Debouncer(120, self._set_volume)
        self.volume_row = rows.scale_row("Volume", None, 0, 100 if kind == "sink" else 150, 50,
                                         lambda v: None if self.updating else self.volume_debounce.trigger(v))
        self.group.add(self.volume_row)

        self.mute_row = Adw.SwitchRow(title="Mute")
        self.mute_row.connect("notify::active", self._on_mute)
        self.group.add(self.mute_row)

        self.empty_row = Adw.ActionRow(title="No device found",
                                       subtitle="Open Health Check: it tells you which driver is missing.")
        self.empty_row.set_visible(False)
        self.group.add(self.empty_row)

    def load(self):
        def got_devices(ok, out, _err):
            devices = []
            if ok:
                try:
                    devices = json.loads(out)
                except ValueError:
                    devices = []
            if self.kind == "source":
                devices = [d for d in devices if not str(d.get("name", "")).endswith(".monitor")]
            self.devices = devices
            run_async(["pactl", f"get-default-{self.kind}"], got_default)

        def got_default(_ok, out, _err):
            default = out.strip()
            self.updating = True
            labels = [d.get("description") or d.get("name", "?") for d in self.devices]
            self.combo.set_model(Gtk.StringList.new(labels))
            has = bool(self.devices)
            for widget in (self.combo, self.volume_row, self.mute_row):
                widget.set_visible(has)
            self.empty_row.set_visible(not has)
            for i, d in enumerate(self.devices):
                if d.get("name") == default:
                    self.combo.set_selected(i)
                    self.volume_row.scale.set_value(_percent(d))
                    self.mute_row.set_active(bool(d.get("mute")))
            self.updating = False

        run_async(["pactl", "-f", "json", "list", f"{self.kind}s"], got_devices)

    def _target(self):
        return "@DEFAULT_SINK@" if self.kind == "sink" else "@DEFAULT_SOURCE@"

    def _on_device(self, combo, _param):
        if self.updating:
            return
        index = combo.get_selected()
        if 0 <= index < len(self.devices):
            name = self.devices[index].get("name")
            run_async(["pactl", f"set-default-{self.kind}", name], lambda *_: self.load())

    def _set_volume(self, value):
        run_async(["pactl", f"set-{self.kind}-volume", self._target(), f"{int(value)}%"])

    def _on_mute(self, row, _param):
        if not self.updating:
            run_async(["pactl", f"set-{self.kind}-mute", self._target(), "1" if row.get_active() else "0"])


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        page = Adw.PreferencesPage()

        self.output = DeviceSection(self, "sink", "Output", "Speakers, headphones, HDMI and Bluetooth audio.")
        page.add(self.output.group)

        self.input = DeviceSection(self, "source", "Microphone", "Your laptop mic, a headset or a USB mic.")
        self.test_row = rows.button_row("Test the microphone", "Records 4 seconds, then plays them back",
                                        "Test", self._test_mic, "audio-input-microphone-symbolic", suggested=True)
        self.input.group.add(self.test_row)
        page.add(self.input.group)

        more = Adw.PreferencesGroup(title="More")
        more.add(rows.link_row("Per-app volume and advanced options", "Opens the audio mixer",
                               lambda: launch([lennox_bin("lennox-open"), "audio_mixer"]), "multimedia-volume-control-symbolic"))
        more.add(rows.link_row("Sound or mic not working?", "Run the health check",
                               lambda: ctx.navigate("health"), "emblem-ok-symbolic"))
        page.add(more)
        self.widget = page

    def refresh(self):
        self.output.load()
        self.input.load()

    def _test_mic(self):
        self.ctx.toast("Recording for 4 seconds, say something…", 4)

        def done(ok, _out, err):
            self.ctx.toast("Did you hear yourself? If not, open the Health Check." if ok
                           else f"Mic test failed: {err.strip()[-100:]}", 5)

        run_async(["bash", "-c", MIC_TEST], done)
