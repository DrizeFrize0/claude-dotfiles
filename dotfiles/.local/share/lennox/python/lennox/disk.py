"""Disk doctor for btrfs: reads the kernel's error messages, says what likely broke the disk,
maps which files are unreadable, removes the harmless ones, and warns at login.

  lennox-disk check          what is wrong and why (reads only)
  lennox-disk map [PATH]     read every file under PATH (default /) and list the unreadable ones
  lennox-disk fix            delete unreadable cache/log files, list the rest (needs a writable disk)
  lennox-disk watch          once at login: warn if the disk reports errors or went read-only
  lennox-disk export DIR     copy the live-USB repair script to DIR (put it on your backup stick)

Nothing here writes to the disk except deleting files you tell it to (fix). Real repairs of the
filesystem itself need the disk unmounted: run lennox-disk-live from a live USB.
"""

import errno
import os
import re
import shutil
import sys
import time

from . import sh

CSUM = re.compile(r"csum failed.*?csum 0x([0-9a-f]+) expected csum 0x([0-9a-f]+)")
TRANSID = re.compile(r"transid verify failed on logical (\d+).*?wanted (\d+) found (\d+)")
PATHED = re.compile(r"checksum error at logical (\d+).*?\(path: (.+?)\)\s*$")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "lennox", "disk-watch")
REPORT = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "lennox", "disk-damage.txt")

# Files that are safe to delete: they are rebuilt automatically.
JUNK_PREFIXES = ("/var/log/", "/var/cache/", "/tmp/", "/var/tmp/")
JUNK_PARTS = ("/.cache/", "/.fabric/tmp/", "/Trash/", "/journal/")


def bits_apart(a, b):
    """How many bits differ between two numbers."""
    return bin(a ^ b).count("1")


def analyze(dmesg_text):
    """Turn kernel messages into findings: which blocks went bad and how."""
    flips, files, seen = [], [], set()
    for line in dmesg_text.splitlines():
        m = CSUM.search(line)
        if m:
            got, want = int(m.group(1), 16), int(m.group(2), 16)
            key = ("c", got, want)
            if key not in seen:
                seen.add(key)
                flips.append({"kind": "checksum", "bits": bits_apart(got, want), "got": hex(got), "want": hex(want)})
        m = TRANSID.search(line)
        if m:
            want, got = int(m.group(2)), int(m.group(3))
            key = ("t", want, got)
            if key not in seen:
                seen.add(key)
                flips.append({"kind": "metadata", "bits": bits_apart(want, got), "got": hex(got), "want": hex(want),
                              "logical": int(m.group(1))})
        m = PATHED.search(line)
        if m and m.group(2) not in files:
            files.append(m.group(2))
    one_bit = [f for f in flips if f["bits"] == 1]
    return {"flips": flips, "one_bit": len(one_bit), "files": files, "metadata": any(f["kind"] == "metadata" for f in flips)}


def parse_stats(text):
    """btrfs device stats output -> {write_io_errs: 0, ...} summed over devices."""
    totals = {}
    for line in text.splitlines():
        m = re.match(r"\[[^\]]+\]\.(\w+)\s+(\d+)", line.strip())
        if m:
            totals[m.group(1)] = totals.get(m.group(1), 0) + int(m.group(2))
    return totals


def is_read_only(mounts_text, target="/"):
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] == target:
            return "ro" in parts[3].split(",")
    return False


def verdict(stats, found):
    """Plain-language conclusion from the counters and the bit differences."""
    io = sum(stats.get(k, 0) for k in ("write_io_errs", "read_io_errs", "flush_io_errs"))
    if io:
        return "drive", "The drive itself reported failed reads or writes. Back up now and plan to replace it."
    if found["one_bit"] >= 2:
        return "ram", ("Every damaged value differs by exactly one bit and the drive reports no I/O errors of its own. "
                       "That is what flipped bits in memory look like: suspect the RAM first (run memtest86+), "
                       "and turn off XMP or any memory overclock in the BIOS.")
    if found["flips"] or stats.get("corruption_errs"):
        return "unknown", "Some data failed its checksum but the cause is not clear. Test the RAM (memtest86+) and read the drive health."
    return "clean", "No errors found."


def read_all(path):
    """Read a whole file in chunks; raises OSError (errno 5) if any part is unreadable."""
    with open(path, "rb") as f:
        while f.read(1 << 20):
            pass


def map_damage(root="/", reader=read_all, skip=("/proc", "/sys", "/dev", "/run", "/tmp"), max_seconds=900):
    """Walk root on one filesystem, read every regular file, and return the unreadable ones."""
    bad, started, count = [], time.time(), 0
    try:
        dev = os.stat(root).st_dev
    except OSError:
        return {"bad": [], "count": 0, "complete": False}
    complete = True
    if root != "/":
        skip = ()  # the skip list is for the whole system only
    for base, dirs, names in os.walk(root, onerror=lambda e: bad.append((e.filename, e.errno))):
        if any(base == s or base.startswith(s + "/") for s in skip):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if _same_fs(os.path.join(base, d), dev)]
        for name in names:
            path = os.path.join(base, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            count += 1
            try:
                reader(path)
            except OSError as e:
                if e.errno in (errno.EIO, errno.EUCLEAN):
                    bad.append((path, e.errno))
        if time.time() - started > max_seconds:
            complete = False
            break
    return {"bad": bad, "count": count, "complete": complete}


def _same_fs(path, dev):
    try:
        return os.lstat(path).st_dev == dev
    except OSError:
        return True


def is_junk(path):
    return path.startswith(JUNK_PREFIXES) or any(p in path for p in JUNK_PARTS)


def fix(bad, remover=os.remove):
    """Delete the unreadable files that are safe to lose. Returns (deleted, kept, failed)."""
    deleted, kept, failed = [], [], []
    for path, _ in bad:
        if not is_junk(path):
            kept.append(path)
            continue
        try:
            remover(path)
            deleted.append(path)
        except OSError as e:
            failed.append((path, e.errno))
    return deleted, kept, failed


def owners(paths):
    """Which pacman package each system file belongs to (so you can reinstall it)."""
    pkgs = set()
    for p in paths:
        if p.startswith(("/usr/", "/etc/", "/opt/", "/boot/")):
            rc, out, _ = sh.run(["pacman", "-Qqo", p], 10)
            if rc == 0 and out.strip():
                pkgs.add(out.strip().splitlines()[0])
    return sorted(pkgs)


# ---------------------------------------------------------------- commands

def _collect():
    rc, dm, _ = sh.run(["dmesg"], 10)
    if rc != 0:
        rc, dm, _ = sh.run(["sudo", "-n", "dmesg"], 10)
    stats = parse_stats(sh.run(["btrfs", "device", "stats", "/"], 10)[1])
    mounts = sh.read_text("/proc/mounts")
    return dm, stats, mounts


def check(out=print):
    dm, stats, mounts = _collect()
    found = analyze(dm)
    kind, text = verdict(stats, found)
    ro = is_read_only(mounts)
    out("Disk check (btrfs)")
    out("  Root filesystem: " + ("READ-ONLY (btrfs switched it off to protect your data)" if ro else "writable"))
    out("  Counters: " + (", ".join("%s=%d" % kv for kv in stats.items()) or "unavailable (run with sudo)"))
    for f in found["flips"]:
        what = "a file's data" if f["kind"] == "checksum" else "the filesystem index"
        out("  Damaged %s: found %s, expected %s (%d bit%s apart)" % (what, f["got"], f["want"], f["bits"], "" if f["bits"] == 1 else "s"))
    for p in found["files"]:
        out("  Damaged file: " + p)
    if found["metadata"]:
        out("  The filesystem index itself is damaged: only an offline repair removes that (lennox-disk-live).")
    out("")
    out("Likely cause: " + kind)
    out(text)
    return 0 if kind == "clean" and not ro else 1


def write_report(result):
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("Unreadable files (%d read, %s)\n" % (result["count"], "complete" if result["complete"] else "stopped early"))
        for path, err in result["bad"]:
            f.write("%s\t%s\n" % (path, errno.errorcode.get(err, err)))


def run_map(root="/", out=print):
    out("Reading every file under %s. This takes a few minutes and writes nothing." % root)
    result = map_damage(root)
    out("Read %d files." % result["count"])
    if not result["bad"]:
        out("Every file is readable.")
        return 0
    out("Unreadable (%d):" % len(result["bad"]))
    for path, err in result["bad"]:
        out("  %s  [%s]%s" % (path, errno.errorcode.get(err, err), "  (safe to delete)" if is_junk(path) else ""))
    write_report(result)
    out("Saved to " + REPORT)
    pkgs = owners([p for p, _ in result["bad"]])
    if pkgs:
        out("Reinstall these packages to replace damaged system files:")
        out("  sudo pacman -S " + " ".join(pkgs))
    out("Next: lennox-disk fix   (deletes the safe ones)")
    return 1


def run_fix(out=print):
    if is_read_only(sh.read_text("/proc/mounts")):
        out("The disk is read-only right now: nothing can be deleted. Reboot, then run this again straight away.")
        return 1
    result = map_damage("/")
    deleted, kept, failed = fix(result["bad"])
    for p in deleted:
        out("Deleted " + p)
    for p, e in failed:
        out("Could not delete %s [%s]: its record is in the damaged index; needs lennox-disk-live" % (p, errno.errorcode.get(e, e)))
    for p in kept:
        out("Kept (not a cache file, restore it from your backup): " + p)
    out("Done: %d deleted, %d kept, %d failed." % (len(deleted), len(kept), len(failed)))
    return 0 if not failed and not kept else 1


def watch(notify=sh.notify):
    """Run at login: tell the user once per problem, never repeat the same message."""
    dm, stats, mounts = _collect()
    state = []
    if is_read_only(mounts):
        state.append("ro")
    if stats.get("corruption_errs"):
        state.append("corrupt%d" % stats["corruption_errs"])
    if sum(stats.get(k, 0) for k in ("write_io_errs", "read_io_errs", "flush_io_errs")):
        state.append("io")
    key = ",".join(state)
    previous = sh.read_text(STATE)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        f.write(key)
    if key and key != previous:
        notify("Your disk needs attention",
               "The disk went read-only or reported data errors. Open a terminal and run: lennox-disk check", "dialog-warning")
    return key


LIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "bin", "lennox-disk-live")


def export(dest, out=print):
    candidates = [LIVE, os.path.expanduser("~/.local/bin/lennox-disk-live")]
    src = next((c for c in candidates if os.path.exists(c)), None)
    if not src or not os.path.isdir(dest):
        out("Could not find the script or the folder " + dest)
        return 1
    target = os.path.join(dest, "lennox-disk-live")
    shutil.copyfile(src, target)
    os.chmod(target, 0o755)
    out("Copied to " + target)
    return 0


def main(argv):
    cmd = argv[0] if argv else "check"
    if cmd == "check":
        return check()
    if cmd == "map":
        return run_map(argv[1] if len(argv) > 1 else "/")
    if cmd == "fix":
        return run_fix()
    if cmd == "watch":
        watch()
        return 0
    if cmd == "export" and len(argv) > 1:
        return export(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
