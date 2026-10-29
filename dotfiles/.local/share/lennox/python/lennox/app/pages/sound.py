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
        # 100% is the most a mic should get: past that it only adds hiss
        self.volume_row = rows.scale_row("Volume", None, 0, 100, 50,
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
        self.clean_row = Adw.SwitchRow(title="Clean microphone",
                                       subtitle="Removes background noise (fans, typing) and echo from the speakers, "
                                                "and keeps your voice at a steady volume")
        self.clean_row.add_prefix(Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic"))
        self.clean_busy = False
        self.clean_row.connect("notify::active", self._on_clean)
        self.input.group.add(self.clean_row)
        page.add(self.input.group)

        self.drivers = Adw.PreferencesGroup(title="Drivers and sound quality",
                                            description="Checks that every sound driver and its firmware loaded, "
                                                        "and the usual causes of a bad sounding mic.")
        actions = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        for label, callback in (("Fix problems", self._fix), ("Save report", self._report)):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _b, cb=callback: cb())
            actions.append(button)
        self.drivers.set_header_suffix(actions)
        self.driver_choices = [("auto", "Automatic"), ("sof", "SOF: newer, needed for built-in digital mics"),
                               ("hda", "HDA: older and simpler (speakers, headphones, headset mic)")]
        self.driver_row = Adw.ComboRow(title="Sound driver",
                                       subtitle="If a sound card won't turn on, try the other one. Needs a restart.")
        self.driver_row.set_model(Gtk.StringList.new([label for _, label in self.driver_choices]))
        self.driver_busy = False
        self.driver_row.connect("notify::selected", self._on_driver)
        self.drivers.add(self.driver_row)
        self.driver_rows = []
        page.add(self.drivers)

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
        self._check()

        def got_clean(ok, out, _err):
            self.clean_busy = True
            self.clean_row.set_active(ok and out.strip() == "on")
            self.clean_busy = False

        run_async([lennox_bin("lennox-sound"), "clean-mic", "status"], got_clean)

        def got_driver(_ok, out, _err):
            values = [v for v, _ in self.driver_choices]
            current = out.strip()
            self.driver_busy = True
            self.driver_row.set_selected(values.index(current) if current in values else 0)
            self.driver_busy = False

        run_async([lennox_bin("lennox-sound"), "driver", "status"], got_driver)

    def _on_driver(self, row, _param):
        if self.driver_busy:
            return
        index = row.get_selected()
        if not 0 <= index < len(self.driver_choices):
            return
        choice = self.driver_choices[index][0]

        def done(ok, _out, _err):
            if ok:
                self.ctx.toast("Sound driver changed. Restart the laptop to use it.", 8)
            else:
                self.ctx.toast("Sound driver not changed", 4)
            self.refresh()

        run_async([lennox_bin("lennox-sound"), "driver", choice], done)

    def _check(self):
        def got(ok, out, _err):
            for row in self.driver_rows:
                self.drivers.remove(row)
            self.driver_rows = []
            try:
                results = json.loads(out)
            except ValueError:
                results = [{"level": "fail", "message": "Could not run the sound check", "hint": "lennox-sound check"}]
            # Problems first, then what is fine
            order = {"fail": 0, "warn": 1, "ok": 2}
            for item in sorted(results, key=lambda r: order.get(r.get("level"), 3)):
                level = item.get("level", "ok")
                row = Adw.ActionRow(title=item.get("message", ""), use_markup=False)
                if level != "ok" and item.get("hint"):
                    row.set_subtitle(item["hint"])
                    row.set_subtitle_selectable(True)
                icon = {"ok": "emblem-ok-symbolic", "warn": "dialog-warning-symbolic"}.get(level, "dialog-error-symbolic")
                image = Gtk.Image.new_from_icon_name(icon)
                image.add_css_class({"ok": "success", "warn": "warning"}.get(level, "error"))
                row.add_prefix(image)
                self.drivers.add(row)
                self.driver_rows.append(row)

        run_async([lennox_bin("lennox-sound"), "check", "--json"], got)

    def _on_clean(self, row, _param):
        if self.clean_busy:
            return
        state = "on" if row.get_active() else "off"
        row.set_sensitive(False)
        self.ctx.toast("Turning the clean microphone " + state + "… (sound restarts for a second)")

        def done(ok, _out, err):
            row.set_sensitive(True)
            if not ok:
                self.ctx.toast(err.strip().splitlines()[-1] if err.strip() else "Could not change the clean microphone", 5)
            self.refresh()

        run_async([lennox_bin("lennox-sound"), "clean-mic", state], done)

    def _fix(self):
        self.ctx.toast("Fixing… (sound restarts for a second)")

        def done(_ok, out, _err):
            lines = [line for line in out.splitlines() if line and not line.startswith("Restarted")]
            failed = [line for line in lines if line.startswith("Could not")]
            fixed = [line for line in lines if not line.startswith("Could not")]
            if failed:
                self.ctx.toast(failed[0], 12)
            elif fixed:
                self.ctx.toast("Fixed: " + "; ".join(fixed), 8)
            else:
                self.ctx.toast("No problems to fix. Sound was restarted.", 6)
            self.refresh()

        run_async([lennox_bin("lennox-sound"), "fix"], done)

    def _report(self):
        def done(ok, out, _err):
            path = next((line[len("Saved: "):] for line in out.splitlines() if line.startswith("Saved: ")), "")
            self.ctx.toast(f"Saved to {path} and copied: paste it to whoever helps you" if ok and path
                           else "Could not save the report", 6)

        run_async([lennox_bin("lennox-sound"), "report"], done)

    def _test_mic(self):
        self.ctx.toast("Recording for 4 seconds, say something…", 4)

        def done(ok, _out, err):
            self.ctx.toast("Did you hear yourself? If not, open the Health Check." if ok
                           else f"Mic test failed: {err.strip()[-100:]}", 5)

        run_async(["bash", "-c", MIC_TEST], done)
