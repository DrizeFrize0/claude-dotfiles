"""Profile: name fallbacks, initials, painting every avatar, installing the picture. Run: python3 tests/test_profile.py"""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp()
os.environ.update(HOME=HOME, XDG_CONFIG_HOME=os.path.join(HOME, ".config"), XDG_CACHE_HOME=os.path.join(HOME, ".cache"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import profile as P, settings as S  # noqa: E402


def size(path):
    out = os.popen(f"identify -format '%w %h' '{path}'").read().strip()
    return tuple(int(x) for x in out.split()) if out else None


class ProfileTest(unittest.TestCase):
    def test_name_fallbacks(self):
        s = S.load()
        s["profile"]["name"] = "  Jado "
        self.assertEqual(P.display_name(s, user="nobody-xyz"), "Jado")
        s["profile"]["name"], s["greeting"]["name"] = "", "J"
        self.assertEqual(P.display_name(s, user="nobody-xyz"), "J")
        s["greeting"]["name"] = ""
        self.assertEqual(P.display_name(s, user="nobody-xyz"), "Nobody-xyz")

    def test_initials(self):
        self.assertEqual(P.initials("Jado Larina"), "JL")
        self.assertEqual(P.initials("jado"), "J")
        self.assertEqual(P.initials("  "), "?")
        self.assertEqual(P.initials("Mary-Jane Watson"), "MW")

    def test_every_avatar_paints_a_square(self):
        d = tempfile.mkdtemp()
        for kind in P.AVATARS:
            out = os.path.join(d, kind + ".png")
            P.paint(kind, out, "Jado")
            with self.subTest(kind=kind):
                self.assertEqual(size(out), (512, 512))

    def test_own_picture_is_cropped_square(self):
        d = tempfile.mkdtemp()
        src, out = os.path.join(d, "wide.jpg"), os.path.join(d, "face.png")
        os.system(f"convert -size 1200x500 gradient:red-blue '{src}'")
        P.from_file(src, out)
        self.assertEqual(size(out), (512, 512))

    def test_install_writes_both_files_in_place(self):
        d = tempfile.mkdtemp()
        face, icon, png = os.path.join(d, ".face"), os.path.join(d, ".face.icon"), os.path.join(d, "x.png")
        P.paint("cat", png)
        open(icon, "w").write("old")
        inode = os.stat(icon).st_ino
        P.install(png, face, icon, setfacl=False)
        self.assertEqual(open(face, "rb").read(), open(png, "rb").read())
        self.assertEqual(os.stat(icon).st_ino, inode)      # same file: the login screen's ACL stays
        self.assertEqual(oct(os.stat(face).st_mode & 0o777), "0o644")

    def test_set_avatar_and_ensure(self):
        P.set_avatar("orbit")
        self.assertEqual(S.load()["profile"]["picture"], "orbit")
        self.assertTrue(os.path.exists(P.FACE) and os.path.exists(P.FACE_ICON))
        os.remove(P.FACE_ICON)
        self.assertTrue(P.ensure())                         # puts the missing copy back
        self.assertFalse(P.ensure())                        # nothing to do

    def test_previews(self):
        paths = P.previews(tempfile.mkdtemp())
        self.assertEqual(set(paths), set(P.AVATARS))


if __name__ == "__main__":
    unittest.main()
