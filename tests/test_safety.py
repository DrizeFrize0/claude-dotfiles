"""Restore points and file copies. Run: python3 tests/test_safety.py"""
import os
import stat
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_STATE_HOME=os.path.join(T, "state"), XDG_CONFIG_HOME=os.path.join(T, "cfg"),
                  LENNOX_SAFETY_SUDO="")
os.makedirs(os.path.join(T, "bin"))
LOG = os.path.join(T, "snapper.log")
with open(os.path.join(T, "bin", "snapper"), "w") as f:
    f.write('''#!/bin/sh
echo "$*" >> %s
case "$*" in
  *"--jsonout list"*) echo '{"root":[{"number":0,"type":"single","date":""},{"number":3,"type":"single","pre-number":null,"date":"Mon 01 Jan","description":"x"},{"number":4,"type":"pre","pre-number":null,"date":"Tue","description":"pacman -Syu"},{"number":5,"type":"post","pre-number":4,"date":"Tue","description":"pacman -Syu"}]}' ;;
  *"create "*) echo 6 ;;
esac
''' % LOG)
os.chmod(os.path.join(T, "bin", "snapper"), 0o755)
os.environ["PATH"] = os.path.join(T, "bin") + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import safety as Z  # noqa: E402

fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    c or fails.append(what)


snaps = Z.list_snapshots()
check([s["number"] for s in snaps] == [3, 4, 5], "restore points listed (snapshot 0 is not one)")
pre, post = Z.last_update_pair(snaps)
check((pre["number"], post["number"]) == (4, 5), "last update = pre 4 / post 5")
check(Z.last_update_pair(snaps[:1]) is None, "no pair when no update was snapshotted")
check(Z.snap("hello") == 6, "snap returns the new number")

done, msg = Z.undo_last_update(ask=lambda _p: "no")
check(not done and "undochange" not in open(LOG).read(), "undo needs the typed word")
done, msg = Z.undo_last_update(yes=True)
log = open(LOG).read()
check(done and "undochange 4..5" in log and "Before undoing" in log, "undo reverts 4..5 after a safety restore point")
check("restart" in msg.lower(), "undo tells you to restart")

# ------------------------------------------------------------ files
home = os.path.join(T, "home")
for d in ("Documents", ".ssh", "Pictures/.cache/x", "Pictures/Cache"):
    os.makedirs(os.path.join(home, d))
open(os.path.join(home, "Documents", "essay.txt"), "w").write("hi")
open(os.path.join(home, "Pictures", "a.png"), "w").write("png")
open(os.path.join(home, "Pictures", "Cache", "junk"), "w").write("junk")
open(os.path.join(home, ".ssh", "id_ed25519"), "w").write("key")
open(os.path.join(home, ".ssh", "id_ed25519.pub"), "w").write("pub")
os.chmod(os.path.join(home, ".ssh", "id_ed25519"), 0o600)
drive = os.path.join(T, "usb")
os.makedirs(drive)
mounts = [(drive, "exfat")]

check(Z.folders() == [n.strip() for n in Z.DEFAULT_FOLDERS.split(",")], "default folders")
check("--no-perms" in Z.rsync_args("exfat", "/a", "/b") and "-a" in Z.rsync_args("ext4", "/a", "/b"),
      "exFAT copies by name and date, Linux drives keep everything")
ok, msg = Z.copy_files(dest=drive, mount_list=mounts, home=home, say=lambda *_: None)
copied = os.path.join(Z.target(drive), "Documents", "essay.txt")
check(ok and os.path.exists(copied), "files copied to the drive: " + msg)
check(not os.path.exists(os.path.join(Z.target(drive), "Pictures", "Cache", "junk")), "caches skipped")
check("(" in msg and ".minecraft" in msg, "missing folders are named, not fatal")
check(Z.load_state()["files"]["folders"] >= 3, "the copy is remembered")
ok, msg = Z.copy_files(dest=drive, mount_list=mounts, home=home, dry=True, say=lambda *_: None)
check(ok and "would be" in msg, "dry run says what would happen")

# restore into an empty home: key permissions come back
home2 = os.path.join(T, "home2")
os.makedirs(home2)
ok, msg = Z.restore_files(source=drive, mount_list=mounts, home=home2, say=lambda *_: None)
key = os.path.join(home2, ".ssh", "id_ed25519")
check(ok and os.path.exists(os.path.join(home2, "Documents", "essay.txt")), "restore brings the files back: " + msg)
check(stat.S_IMODE(os.stat(key).st_mode) == 0o600 and stat.S_IMODE(os.stat(os.path.dirname(key)).st_mode) == 0o700,
      "restore makes the private key private again")
ok, msg = Z.restore_files(source=os.path.join(T, "nothing"), mount_list=mounts, home=home2, say=lambda *_: None)
check(not ok and "Plug" in msg, "no copy found says what to do")

# ------------------------------------------------------------ advice
info = {"snapper": True, "snapshots": 3, "files_days": None, "remind_days": 14}
check(any(l == "warn" and "never" in t for l, t, _h in Z.advice(info)), "never copied -> warns")
info["files_days"] = 30
check(any("30 days" in t for _l, t, _h in Z.advice(info)), "old copy -> warns with the age")
info["files_days"] = 2
check(all(l == "ok" for l, _t, _h in Z.advice(info)), "fresh copy and snapshots -> all ok")
check(Z.days_since(1000, now=1000 + 86400 * 3 + 5) == 3 and Z.days_since(None) is None, "days_since")
print("OK safety" if not fails else "FAILED safety: %d" % len(fails))
sys.exit(1 if fails else 0)
