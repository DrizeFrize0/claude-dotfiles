"""Automatic game mode and the ping check (no desktop needed)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import gameprofiles as GP  # noqa: E402
from lennox import ping  # noqa: E402


def win(cls="", title="", mapped=True):
    return {"class": cls, "initialClass": cls, "title": title, "mapped": mapped}


class Detect(unittest.TestCase):
    def test_games(self):
        for c in (win("steam_app_730"), win("gamescope"), win("Minecraft* 1.21.1"), win("java", "Minecraft 1.20.4"),
                  win("net.minecraft.client"), win("dolphin-emu"), win("steam_app_0", "Hades")):
            self.assertTrue(GP.is_game_client(c), c)

    def test_not_games(self):
        for c in (win("firefox", "Minecraft wiki"), win("kitty"), win("steam", "Steam"), win("vesktop"), win("java", "IntelliJ"),
                  win("steam_app_730", mapped=False)):
            self.assertFalse(GP.is_game_client(c), c)

    def test_extra_words(self):
        self.assertTrue(GP.is_game_client(win("MyGame.exe"), ("mygame",)))
        self.assertTrue(GP.is_game_client(win("x", "Some Title Here"), ("title here",)))
        self.assertFalse(GP.is_game_client(win("kitty"), ("",)))


class Auto(unittest.TestCase):
    def test_actions(self):
        self.assertEqual(GP.auto_action(False, False, True), "on")
        self.assertIsNone(GP.auto_action(True, True, True))
        self.assertEqual(GP.auto_action(True, True, False), "off")
        self.assertIsNone(GP.auto_action(False, True, False))       # you turned it on by hand: leave it
        self.assertIsNone(GP.auto_action(False, True, True))
        self.assertIsNone(GP.auto_action(False, False, False))


class Ping(unittest.TestCase):
    OUT = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
--- 1.1.1.1 ping statistics ---
8 packets transmitted, 8 received, 0% packet loss, time 1403ms
rtt min/avg/max/mdev = 12.100/18.250/40.300/9.120 ms"""

    def test_parse(self):
        r = ping.parse_ping(self.OUT)
        self.assertEqual((r["min"], r["avg"], r["max"], r["jitter"], r["loss"]), (12.1, 18.25, 40.3, 9.12, 0.0))
        self.assertIsNone(ping.parse_ping("8 packets transmitted, 0 received, 100% packet loss"))

    def test_advice(self):
        good = {"router": {"avg": 3, "jitter": 1, "loss": 0}, "internet": {"avg": 25, "jitter": 2, "loss": 0}}
        self.assertEqual(ping.advice(good, {"ssid": "A", "signal": 90, "ghz": 5}, False), ["Your connection looks good for gaming."])
        bad = {"router": {"avg": 40, "jitter": 20, "loss": 2}, "internet": {"avg": 150, "jitter": 5, "loss": 0}}
        tips = " ".join(ping.advice(bad, {"ssid": "A", "signal": 40, "ghz": 2.4}, True))
        for word in ("weak", "5 GHz", "power saving", "router", "bumpy", "lost"):
            self.assertIn(word, tips)


if __name__ == "__main__":
    unittest.main()
