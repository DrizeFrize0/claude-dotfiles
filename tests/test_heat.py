"""lennox-heat: the diagnosis picks the right causes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import heat  # noqa: E402


def snap(**kw):
    base = {"temp": 99.0, "load": 5.0, "procs": [(3.0, "spotify", "spotify")], "freq": 1500, "power_mode": "balanced", "game_mode": False,
            "turbo_off": False, "cap": 100, "epp": "balance_performance", "fans": [3200], "gpu_awake": False, "throttled": 0,
            "extras": [], "livewall": False}
    base.update(kw)
    return base


def whats(s):
    return " | ".join(f"{w} -> {t}" for w, t in heat.diagnose(s))


class Diagnose(unittest.TestCase):
    def test_busy_process(self):
        self.assertIn("firefox is using 180%", whats(snap(procs=[(180.0, "firefox", "firefox")])))

    def test_max_mode_and_game_mode(self):
        w = whats(snap(power_mode="max", game_mode=True))
        self.assertIn("Max performance", w)
        self.assertIn("Game mode is on", w)

    def test_fast_clock_at_idle(self):
        self.assertIn("GHz while almost nothing", whats(snap(freq=4200)))
        self.assertNotIn("GHz while", whats(snap(freq=4200, turbo_off=True)))

    def test_extras_and_wallpaper_and_gpu(self):
        w = whats(snap(extras=["pet", "cursorfx"], livewall=True, gpu_awake=True))
        for word in ("pet, cursorfx", "live (video) wallpaper", "NVIDIA"):
            self.assertIn(word, w)

    def test_hardware_hint_only_when_nothing_else(self):
        self.assertIn("points at the hardware", whats(snap()))
        self.assertNotIn("points at the hardware", whats(snap(game_mode=True)))
        self.assertNotIn("points at the hardware", whats(snap(temp=50.0)))

    def test_fans(self):
        self.assertIn("doesn't report its fan", whats(snap(fans=[])))
        self.assertIn("0 rpm", whats(snap(fans=[0])))

    def test_throttling(self):
        self.assertIn("slowed itself down", whats(snap(throttled=42)))

    def test_report_mentions_hardware_tips_when_hot(self):
        self.assertIn("thermal paste", heat.report(snap()))
        self.assertNotIn("thermal paste", heat.report(snap(temp=45.0)))


if __name__ == "__main__":
    unittest.main()
