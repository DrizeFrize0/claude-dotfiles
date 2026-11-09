"""Disk doctor: reads the real error lines from Jado's laptop, maps damage, cleans junk. Run: python3 tests/test_disk.py"""
import errno
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import disk  # noqa: E402

DMESG = """\
[11150.702388] BTRFS warning (device nvme0n1p7 state EA): csum failed root 258 ino 310 off 12443648 csum 0x8ebd1420 expected csum 0x8ebd1c20 mirror 1
[84.248174] BTRFS warning (device nvme0n1p7 state EA): scrub: checksum error at logical 40545497088 on dev /dev/nvme0n1p7, physical 41627627520 root 258 inode 310 offset 12304384 length 4096 links 1 (path: journal/7e0f/system@e5d0.journal)
[136.904883] BTRFS error (device nvme0n1p7): parent transid verify failed on logical 79322087424 mirror 1 wanted 533610 found 9322
[136.905098] BTRFS error (device nvme0n1p7): parent transid verify failed on logical 79322087424 mirror 2 wanted 533610 found 9322
"""
STATS = """[/dev/nvme0n1p7].write_io_errs    0
[/dev/nvme0n1p7].read_io_errs     0
[/dev/nvme0n1p7].flush_io_errs    0
[/dev/nvme0n1p7].corruption_errs  6
[/dev/nvme0n1p7].generation_errs  0
"""


class DiskTest(unittest.TestCase):
    def test_one_bit_differences_found(self):
        self.assertEqual(disk.bits_apart(0x8ebd1420, 0x8ebd1c20), 1)
        self.assertEqual(disk.bits_apart(533610, 9322), 1)

    def test_analyze_real_messages(self):
        found = disk.analyze(DMESG)
        self.assertEqual(len(found["flips"]), 2)  # both mirrors of the metadata block count once
        self.assertEqual(found["one_bit"], 2)
        self.assertTrue(found["metadata"])
        self.assertEqual(found["files"], ["journal/7e0f/system@e5d0.journal"])

    def test_verdict_points_at_ram_when_no_io_errors(self):
        kind, text = disk.verdict(disk.parse_stats(STATS), disk.analyze(DMESG))
        self.assertEqual(kind, "ram")
        self.assertIn("memtest86+", text)

    def test_verdict_drive_when_io_errors(self):
        stats = disk.parse_stats(STATS.replace("read_io_errs     0", "read_io_errs     4"))
        self.assertEqual(disk.verdict(stats, disk.analyze(DMESG))[0], "drive")

    def test_verdict_clean(self):
        self.assertEqual(disk.verdict({"corruption_errs": 0}, disk.analyze(""))[0], "clean")

    def test_read_only_detection(self):
        self.assertTrue(disk.is_read_only("/dev/x / btrfs ro,relatime 0 0\n"))
        self.assertFalse(disk.is_read_only("/dev/x / btrfs rw,relatime 0 0\n"))
        self.assertFalse(disk.is_read_only("/dev/x /home btrfs ro 0 0\n"))

    def test_map_finds_unreadable_files_and_fix_deletes_only_junk(self):
        root = tempfile.mkdtemp(dir=os.path.expanduser("~"))  # not under /tmp, which counts as junk
        self.addCleanup(shutil.rmtree, root, True)
        for rel in ("good.txt", "docs/essay.txt", ".cache/app/blob", "var/log/journal/a.journal"):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write("x")

        def reader(path):
            if path.endswith(("essay.txt", "blob", "a.journal")):
                raise OSError(errno.EIO, "Input/output error")

        res = disk.map_damage(root, reader=reader)
        bad = sorted(os.path.relpath(p, root) for p, _ in res["bad"])
        self.assertEqual(bad, [".cache/app/blob", "docs/essay.txt", "var/log/journal/a.journal"])
        self.assertTrue(res["complete"])
        removed = []
        deleted, kept, failed = disk.fix(res["bad"], remover=removed.append)
        self.assertEqual(sorted(os.path.relpath(p, root) for p in deleted), [".cache/app/blob", "var/log/journal/a.journal"])
        self.assertEqual([os.path.relpath(p, root) for p in kept], ["docs/essay.txt"])
        self.assertEqual(failed, [])

    def test_fix_reports_files_it_cannot_delete(self):
        def refuse(path):
            raise OSError(errno.EIO, "x")
        deleted, kept, failed = disk.fix([("/home/x/.cache/y", errno.EIO)], remover=refuse)
        self.assertEqual((deleted, kept), ([], []))
        self.assertEqual(failed[0][0], "/home/x/.cache/y")

    def test_watch_tells_once(self):
        calls = []
        orig = (disk._collect, disk.STATE)
        disk.STATE = os.path.join(tempfile.mkdtemp(), "state")
        disk._collect = lambda: ("", disk.parse_stats(STATS), "/dev/x / btrfs ro 0 0\n")
        try:
            first = disk.watch(notify=lambda *a: calls.append(a))
            second = disk.watch(notify=lambda *a: calls.append(a))
        finally:
            disk._collect, disk.STATE = orig
        self.assertEqual(first, second)
        self.assertEqual(first, "ro,corrupt6")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
