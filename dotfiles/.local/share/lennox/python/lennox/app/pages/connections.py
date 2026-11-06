"""Wi-Fi and Bluetooth."""

from gi.repository import Adw

from .. import rows
from ..util import launch, lennox_bin, run_async


class Page:
    def __init__(self, ctx):
        self.ctx = ctx
        self.updating = False
        page = Adw.PreferencesPage()

        wifi = Adw.PreferencesGroup(title="Wi-Fi")
        self.wifi_switch = Adw.SwitchRow(title="Wi-Fi")
        self.wifi_switch.connect("notify::active", self._toggle_wifi)
        wifi.add(self.wifi_switch)
        self.wifi_status = rows.info_row("Connected to", "…")
        wifi.add(self.wifi_status)
        wifi.add(rows.link_row("Choose a network", "Also: click the Wi-Fi icon in the bar",
                               lambda: launch([lennox_bin("lennox-menu"), "wifi"]), "network-wireless-symbolic"))
        wifi.add(rows.link_row("Network settings", "School/work logins (WPA2-Enterprise), VPN, hotspots, wired",
                               lambda: launch(["nm-connection-editor"]), "preferences-system-network-symbolic"))
        page.add(wifi)

        net = Adw.PreferencesGroup(
            title="Internet, cable and DNS",
            description="Lennox blocks nothing on the network. If sites don't open (on a cable or Wi-Fi), Check finds out why "
                        "and Fix puts it right. The DNS is the address book your laptop asks for every site: a fast one makes "
                        "everything feel quicker.")
        net.add(rows.combo_row(ctx.store, "network.dns", "DNS",
                               [("auto", "Automatic (what the network hands out)"), ("fastest", "The fastest one (Lennox tests them)"),
                                ("cloudflare", "Cloudflare (1.1.1.1)"), ("google", "Google (8.8.8.8)"), ("quad9", "Quad9 (9.9.9.9)")]))
        self.net_result = rows.info_row("Result", "Not checked yet")
        self.net_result.value_label.set_wrap(True)
        net.add(self.net_result)
        net.add(rows.button_row("Check my connection", "Tests the cable, DNS, IPv6, sites and anything left blocking", "Check",
                                lambda: self._net("check"), "network-wired-symbolic"))
        net.add(rows.button_row("Fix what it finds", "Removes a leftover site block, switches to a fast DNS, turns off broken IPv6",
                                "Fix", lambda: self._net("fix", "--yes"), "emblem-ok-symbolic", suggested=True))
        page.add(net)

        bt = Adw.PreferencesGroup(title="Bluetooth")
        self.bt_switch = Adw.SwitchRow(title="Bluetooth")
        self.bt_switch.connect("notify::active", self._toggle_bt)
        bt.add(self.bt_switch)
        bt.add(rows.link_row("Bluetooth devices", "Pair headphones, controllers, mice…",
                             lambda: launch(["blueman-manager"]), "bluetooth-symbolic"))
        page.add(bt)
        self.widget = page

    def refresh(self):
        def got_radio(ok, out, _err):
            self.updating = True
            self.wifi_switch.set_active(ok and out.strip() == "enabled")
            self.updating = False

        def got_connection(ok, out, _err):
            names = [line.split(":", 1)[1] for line in out.splitlines()
                     if ok and line.startswith(("802-11-wireless:", "802-3-ethernet:"))]
            self.wifi_status.value_label.set_label(", ".join(n for n in names if n) or "Not connected")

        def got_bt(ok, out, _err):
            self.updating = True
            self.bt_switch.set_active(ok and "Powered: yes" in out)
            self.bt_switch.set_sensitive(ok and "Controller" in out)
            if not (ok and "Controller" in out):
                self.bt_switch.set_subtitle("No Bluetooth adapter found")
            self.updating = False

        run_async(["nmcli", "radio", "wifi"], got_radio)
        run_async(["nmcli", "-t", "-f", "TYPE,NAME", "connection", "show", "--active"], got_connection)
        run_async(["bluetoothctl", "show"], got_bt)

    def _toggle_wifi(self, row, _param):
        if not self.updating:
            run_async(["nmcli", "radio", "wifi", "on" if row.get_active() else "off"],
                      lambda *_: self.refresh())

    def _toggle_bt(self, row, _param):
        if self.updating:
            return
        if row.get_active():
            cmd = "rfkill unblock bluetooth; sleep 1; bluetoothctl power on"
        else:
            cmd = "bluetoothctl power off"
        run_async(["bash", "-c", cmd], lambda *_: self.refresh())

    def _net(self, *args):
        self.net_result.value_label.set_label("Working… (about 15 seconds)")

        def done(ok, out, err):
            self.net_result.value_label.set_label((out.strip() or err.strip() or "No answer") if ok or out.strip() else (err.strip() or "Couldn't run it"))
        run_async([lennox_bin("lennox-net"), *args], done)
