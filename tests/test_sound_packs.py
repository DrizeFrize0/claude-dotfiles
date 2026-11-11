"""Sound packs: every event in every pack is a clean, short WAV; the setting picks the pack. Run: python3 tests/test_sound_packs.py"""
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import settings as S, sounds  # noqa: E402


class PackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        for pack in sounds.TIMBRES:
            sounds.make_pack(pack, cls.dir)

    def read(self, pack, event):
        with wave.open(os.path.join(self.dir, pack, event + ".wav")) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, sounds.RATE))
            n = w.getnframes()
            return struct.unpack("<%dh" % n, w.readframes(n))

    def test_every_event_every_pack(self):
        for pack in sounds.TIMBRES:
            for event in sounds.EVENTS:
                data = self.read(pack, event)
                with self.subTest(pack=pack, event=event):
                    self.assertTrue(0.05 < len(data) / sounds.RATE < 2.0)
                    self.assertLessEqual(max(abs(x) for x in data), 0.71 * 32767)   # headroom, no clipping
                    self.assertLess(abs(data[0]), 400)                             # no click at the start
                    self.assertEqual(data[-1], 0)                                  # nor at the end

    def test_packs_sound_different(self):
        a, b = self.read("soft", "notification"), self.read("glass", "notification")
        self.assertNotEqual(a[2000:2100], b[2000:2100])

    def test_sound_file_builds_on_first_use(self):
        d = tempfile.mkdtemp()
        path = sounds.sound_file("plug", pack="pop", folder=d)
        self.assertTrue(path and path.endswith("pop/plug.wav") and os.path.exists(path))

    def test_freedesktop_uses_the_theme(self):
        theme = tempfile.mkdtemp()
        open(os.path.join(theme, "power-plug.oga"), "w").close()
        self.assertEqual(sounds.sound_file("plug", theme=theme, pack="freedesktop"), os.path.join(theme, "power-plug.oga"))

    def test_setting(self):
        self.assertEqual(S.DEFAULTS["sounds"]["pack"], "soft")
        self.assertEqual(S.CHOICES[("sounds", "pack")], ["soft", "glass", "pop", "freedesktop"])


if __name__ == "__main__":
    unittest.main()
