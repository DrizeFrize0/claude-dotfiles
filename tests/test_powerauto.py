"""Automatic power mode: the rule, hysteresis, manual changes, game mode, and the messages."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import powerauto as PA  # noqa: E402
from lennox import settings as S  # noqa: E402

CFG = dict(S.DEFAULTS["power"])


def run(brain, steps, cfg=CFG):
    """steps: (on_ac, capacity, current, game). Returns every action, in order."""
    out = []
    for on_ac, cap, cur, game in steps:
        out.append(brain.tick(cfg, on_ac, cap, cur, game))
    return out


class Rule(unittest.TestCase):
    def test_the_three_cases(self):
        self.assertEqual(PA.decide(True, 100, None, CFG)[0], "performance")
        self.assertEqual(PA.decide(True, 15, None, CFG)[0], "performance")           # plugged in at any level
        self.assertEqual(PA.decide(False, 100, None, CFG)[0], "balanced")
        self.assertEqual(PA.decide(False, 80, None, CFG)[0], "balanced")             # 80 itself is still balanced
        self.assertEqual(PA.decide(False, 79, None, CFG)[0], "power-saver")
        self.assertEqual(PA.decide(False, 5, None, CFG)[0], "power-saver")

    def test_reasons_are_plain(self):
        self.assertEqual(PA.decide(True, 50, None, CFG)[2], "plugged in")
        self.assertIn("below 80%", PA.decide(False, 60, None, CFG)[2])
        self.assertIn("at least 80%", PA.decide(False, 90, None, CFG)[2])

    def test_hysteresis_stops_flapping_at_the_threshold(self):
        # once in the low band, it takes 82% (threshold + 2) to go back up
        self.assertEqual(PA.decide(False, 81, "low", CFG)[0], "power-saver")
        self.assertEqual(PA.decide(False, 82, "low", CFG)[0], "balanced")
        self.assertEqual(PA.decide(False, 81, "high", CFG)[0], "balanced")

    def test_your_own_numbers(self):
        cfg = dict(CFG, threshold=50, ac_mode="balanced", battery_low_mode="balanced")
        self.assertEqual(PA.decide(True, 90, None, cfg)[0], "balanced")
        self.assertEqual(PA.decide(False, 49, None, cfg)[0], "balanced")


class Brain(unittest.TestCase):
    def test_login_on_the_charger_sets_performance_and_says_so(self):
        b = PA.Brain()
        steps = run(b, [(True, 100, "balanced", False), (True, 100, "performance", False)])
        self.assertEqual(steps[0], [("set", "performance")])
        self.assertEqual(steps[1], [("notify", "performance", "plugged in")])

    def test_unplug_then_the_battery_drains_past_80(self):
        b = PA.Brain()
        run(b, [(True, 100, "performance", False), (True, 100, "performance", False)])
        a = run(b, [(False, 95, "performance", False), (False, 95, "balanced", False),     # unplug: balanced
                    (False, 81, "balanced", False),                                          # nothing to do
                    (False, 79, "balanced", False), (False, 79, "power-saver", False),     # crosses 80: power saver
                    (False, 60, "power-saver", False)])                                      # still nothing
        self.assertEqual(a[0], [("set", "balanced")])
        self.assertEqual(a[1], [("notify", "balanced", "on battery, 95% (at least 80%)")])
        self.assertEqual(a[2], [])
        self.assertEqual(a[3], [("set", "power-saver")])
        self.assertEqual(a[4][0][:2], ("notify", "power-saver"))
        self.assertIn("below 80%", a[4][0][2])
        self.assertEqual(a[5], [])

    def test_plugging_back_in_returns_to_performance(self):
        b = PA.Brain()
        run(b, [(False, 50, "power-saver", False), (False, 50, "power-saver", False)])
        a = run(b, [(True, 50, "power-saver", False)])
        self.assertEqual(a[0], [("set", "performance")])

    def test_a_mode_you_pick_stays_until_something_changes(self):
        b = PA.Brain()
        run(b, [(True, 100, "performance", False), (True, 100, "performance", False)])
        a = run(b, [(True, 100, "power-saver", False),                                       # you pick power saver on the charger
                    (True, 100, "power-saver", False), (True, 100, "power-saver", False)])
        self.assertEqual(a[0], [("notify", "power-saver", "changed by you or another program")])
        self.assertEqual(a[1], [])                                                           # the rule leaves it alone
        self.assertEqual(a[2], [])
        a = run(b, [(False, 90, "power-saver", False)])                                      # but unplugging is a real change
        self.assertEqual(a[0], [("set", "balanced")])

    def test_game_mode_is_left_alone(self):
        b = PA.Brain()
        run(b, [(False, 90, "balanced", False), (False, 90, "balanced", False)])
        a = run(b, [(False, 70, "performance", True), (False, 70, "performance", True)])    # game mode asks for performance
        self.assertNotIn(("set", "power-saver"), a[0] + a[1])
        a = run(b, [(False, 70, "balanced", False)])                                         # game over, game mode restored balanced
        self.assertIn(("set", "power-saver"), a[0])                                          # now the rule catches up

    def test_off_means_no_changes_but_still_messages(self):
        cfg = dict(CFG, auto=False)
        b = PA.Brain()
        a = run(b, [(True, 100, "balanced", False), (True, 100, "max-whatever", False)], cfg)
        self.assertFalse([x for step in a for x in step if x[0] == "set"])
        self.assertEqual(a[1][0][0], "notify")

    def test_messages_off(self):
        cfg = dict(CFG, notify_changes=False)
        b = PA.Brain()
        a = run(b, [(True, 100, "balanced", False), (True, 100, "performance", False)], cfg)
        self.assertFalse([x for step in a for x in step if x[0] == "notify"])

    def test_desktop_does_nothing(self):
        b = PA.Brain()
        self.assertEqual(run(b, [(None, None, "balanced", False)])[0], [])

    def test_same_mode_picked_again_is_not_called_ours(self):
        b = PA.Brain()
        run(b, [(True, 100, "balanced", False), (True, 100, "performance", False)])
        run(b, [(True, 100, "power-saver", False)])
        a = run(b, [(True, 100, "performance", False)])                                      # you go back to performance yourself
        self.assertEqual(a[0], [("notify", "performance", "changed by you or another program")])


class Settings(unittest.TestCase):
    def test_defaults_and_limits(self):
        self.assertEqual((CFG["auto"], CFG["ac_mode"], CFG["battery_high_mode"], CFG["battery_low_mode"], CFG["threshold"]),
                         (True, "performance", "balanced", "power-saver", 80))
        merged = S.merge({"power": {"threshold": 5, "ac_mode": "turbo-nonsense", "battery_low_mode": "balanced"}})["power"]
        self.assertEqual(merged["threshold"], 20)                                            # kept inside 20 to 95
        self.assertEqual(merged["ac_mode"], "performance")                                   # a wrong word falls back
        self.assertEqual(merged["battery_low_mode"], "balanced")


if __name__ == "__main__":
    unittest.main()
