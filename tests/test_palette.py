"""Command palette: every entry runs a real Lennox command. Run: python3 tests/test_palette.py"""
import os
import shlex
import sys
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(R, "dotfiles", ".local", "share", "lennox", "python"))
from lennox import palette, settings as S  # noqa: E402

BIN = os.path.join(R, "dotfiles", ".local", "bin")


def programs(command):
    argv = shlex.split(command)
    if argv[0] == "sh":                       # sh -c 'a && b'
        return [part.split()[0] for part in argv[2].split("&&")]
    if argv[0] == "kitty":                    # kitty --hold PROGRAM
        return [argv[2]]
    return [argv[0]]


class PaletteTest(unittest.TestCase):
    def setUp(self):
        self.items = palette.entries(themes=[("ocean", "Ocean")])

    def test_every_command_exists(self):
        for title, _icon, command in self.items:
            for prog in programs(command):
                with self.subTest(title=title):
                    self.assertTrue(os.path.exists(os.path.join(BIN, prog)), f"{title}: {prog} missing")

    def test_settings_pages_read_without_gtk(self):
        pages = palette.settings_pages()
        self.assertGreater(len(pages), 25)
        self.assertIn(("health", "Health Check", "emblem-ok-symbolic"), pages)

    def test_every_bar_style_and_sound_pack(self):
        self.assertEqual([s for s, _ in palette.BAR_STYLES], S.CHOICES[("bar", "style")])
        self.assertEqual([p for p, _ in palette.SOUND_PACKS], S.CHOICES[("sounds", "pack")])

    def test_titles_unique_and_rofi_format(self):
        titles = [t for t, _, _ in self.items]
        self.assertEqual(len(titles), len(set(titles)))
        lines = palette.rofi_lines(self.items[:2]).splitlines()
        self.assertEqual(lines[0], f"{self.items[0][0]}\0icon\x1f{self.items[0][1]}")

    def test_color_theme_entry(self):
        self.assertIn(("Color theme: Ocean", "applications-graphics-symbolic", "lennox-theme set ocean"), self.items)


if __name__ == "__main__":
    unittest.main()
