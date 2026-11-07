"""overlay.Cached: a check that starts a program must not run on every frame. Run with the system python (it needs GTK)."""
import os
import sys
import unittest

os.environ["LENNOX_WIDGETS_NO_LAYER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import overlay  # noqa: E402


class Cache(unittest.TestCase):
    def test_runs_once_per_ttl(self):
        now, calls = [0.0], []
        c = overlay.Cached(lambda: calls.append(1) or len(calls), 2.0, clock=lambda: now[0])
        values = []
        for t in (0.0, 0.1, 0.5, 1.9, 2.0, 2.1, 3.9, 4.0):          # 8 frames
            now[0] = t
            values.append(c())
        self.assertEqual(len(calls), 3)                              # at 0, 2.0 and 4.0
        self.assertEqual(values, [1, 1, 1, 1, 2, 2, 2, 3])

    def test_remembers_none_too(self):
        now, calls = [0.0], []
        c = overlay.Cached(lambda: calls.append(1), 5.0, clock=lambda: now[0])
        c(); c(); c()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
