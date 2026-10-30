"""Auto cleanup: old package downloads, unused packages, logs, trash, caches.

    python3 -m lennox.cleanup scan [--json]   what can go, and how big it is
    python3 -m lennox.cleanup now [IDS...]    clean (asks for your password once for system parts)
    python3 -m lennox.cleanup auto            the weekly run: your own files only, no password
    python3 -m lennox.cleanup root IDS...     (as root, through pkexec) the system parts

Nothing you made is touched: only downloads that can be fetched again,
packages nothing uses, old logs, and trash you threw away a while ago.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

from . import settings as S

HOME = os.path.expanduser("~")
TRASH = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share"), "Trash")
CACHE = os.environ.get("XDG_CACHE_HOME") or os.path.join(HOME, ".cache")
JOURNAL_KEEP = "200M"
THUMBNAIL_DAYS = 30
LAST = os.path.join(S.STATE_DIR, "cleanup.json")

# id: (title, needs root)
ITEMS = {
    "packages": ("Old package downloads", True),
    "orphans": ("Packages nothing uses", True),
    "journal": ("Old system logs", True),
    "aur": ("AUR build files", False),
    "flatpak": ("Unused Flatpak runtimes", False),
    "trash": ("Trash", False),
    "thumbnails": ("Old thumbnails", False),
}
ROOT_IDS = [i for i, (_, root) in ITEMS.items() if root]


def human(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return ""


UNITS = {"B": 1, "K": 1024, "KB": 1024, "KIB": 1024, "M": 1024 ** 2, "MB": 1024 ** 2, "MIB": 1024 ** 2,
         "G": 1024 ** 3, "GB": 1024 ** 3, "GIB": 1024 ** 3, "T": 1024 ** 4, "TB": 1024 ** 4, "TIB": 1024 ** 4}


def parse_size(text):
    """'1.2 GiB', '512.0M', '200 MiB' -> bytes (0 if it can't tell)."""
    m = re.search(r"([\d.]+)\s*([KMGT]?i?B?)\b", text.strip(), re.I)
    if not m:
        return 0
    try:
        return int(float(m.group(1)) * UNITS.get(m.group(2).upper() or "B", 1))
    except ValueError:
        return 0


def _run(argv, timeout=60):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def _tree_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _remove(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------- each part: (size, detail) and clean

def old_trash(days, trash=TRASH, now=None):
    """[(path in files/, path of .trashinfo)] thrown away more than `days` ago (0 = all)."""
    now = time.time() if now is None else now
    found = []
    info_dir = os.path.join(trash, "info")
    try:
        names = os.listdir(info_dir)
    except OSError:
        return found
    for name in names:
        if not name.endswith(".trashinfo"):
            continue
        info = os.path.join(info_dir, name)
        when = None
        try:
            with open(info, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("DeletionDate="):
                        when = time.mktime(time.strptime(line.split("=", 1)[1].strip()[:19], "%Y-%m-%dT%H:%M:%S"))
        except (OSError, ValueError):
            pass
        if when is None:
            try:
                when = os.path.getmtime(info)
            except OSError:
                continue
        if days == 0 or now - when >= days * 86400:
            found.append((os.path.join(trash, "files", name[:-len(".trashinfo")]), info))
    return found


def scan_trash(days):
    items = old_trash(days)
    size = sum(_tree_size(f) if os.path.isdir(f) else (os.path.getsize(f) if os.path.exists(f) else 0)
               for f, _ in items)
    what = "everything in it" if days == 0 else f"thrown away over {days} days ago"
    return size, f"{len(items)} item{'s' * (len(items) != 1)}, {what}" if items else "Nothing old enough"


def clean_trash(days):
    for path, info in old_trash(days):
        _remove(path)
        _remove(info)


def old_thumbnails(days=THUMBNAIL_DAYS, root=None, now=None):
    root = root or os.path.join(CACHE, "thumbnails")
    now = time.time() if now is None else now
    found = []
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            try:
                if now - os.stat(path).st_atime >= days * 86400:
                    found.append(path)
            except OSError:
                pass
    return found


def aur_dirs():
    return [d for d in (os.path.join(CACHE, "yay"), os.path.join(CACHE, "paru", "clone")) if os.path.isdir(d)]


def scan_aur():
    size = sum(_tree_size(d) for d in aur_dirs())
    return size, "Downloaded again when an AUR app updates" if size else "Nothing to clean"


def clean_aur():
    for folder in aur_dirs():
        for name in os.listdir(folder):
            _remove(os.path.join(folder, name))


def scan_flatpak():
    if not shutil.which("flatpak"):
        return 0, "Flatpak is not installed"
    return 0, "Runtimes no app needs anymore (size shown after cleaning)"


def clean_flatpak():
    if shutil.which("flatpak"):
        _run(["flatpak", "uninstall", "--unused", "--noninteractive", "--assumeyes"], timeout=600)


def orphans():
    """Installed as a dependency, needed by nothing (not even optionally)."""
    if not shutil.which("pacman"):
        return []
    code, out, _ = _run(["pacman", "-Qdttq"])
    return out.split() if code == 0 else []


def scan_orphans():
    names = orphans()
    if not names:
        return 0, "Nothing to clean"
    _, out, _ = _run(["pacman", "-Qi", *names])
    size = sum(parse_size(line.split(":", 1)[1]) for line in out.splitlines() if line.startswith("Installed Size"))
    shown = ", ".join(names[:6]) + (f" and {len(names) - 6} more" if len(names) > 6 else "")
    return size, shown


def scan_packages():
    """Keeps the 2 newest downloads of each installed package (to roll back) and none of removed ones."""
    if not shutil.which("paccache"):
        return 0, "Needs pacman-contrib"
    size, count = 0, 0
    for args in (["-dvk2"], ["-dvuk0"]):
        _, out, _ = _run(["paccache", *args])
        m = re.search(r"(\d+) candidates? \(disk space saved: ([^)]+)\)", out)
        if m:
            count += int(m.group(1))
            size += parse_size(m.group(2))
    return size, (f"{count} old download{'s' * (count != 1)} (the newest 2 of each are kept)"
                  if count else "Nothing to clean")


def scan_journal():
    if not shutil.which("journalctl"):
        return 0, "Nothing to clean"
    _, out, _ = _run(["journalctl", "--disk-usage"])
    m = re.search(r"take up ([\d.]+\s*[KMGT]?i?B?)", out)
    used = parse_size(m.group(1)) if m else 0
    extra = max(0, used - parse_size(JOURNAL_KEEP))
    return extra, (f"Logs use {human(used)}; the newest {JOURNAL_KEEP}B are kept" if extra
                   else "Nothing to clean")


SCANS = {"packages": scan_packages, "orphans": scan_orphans, "journal": scan_journal, "aur": scan_aur,
         "flatpak": scan_flatpak, "thumbnails": None, "trash": None}


def scan(ids=None, settings=None):
    settings = settings or S.load()
    days = settings["cleanup"]["trash_days"]
    out = []
    for item, (title, root) in ITEMS.items():
        if ids and item not in ids:
            continue
        if item == "trash":
            size, detail = scan_trash(days)
        elif item == "thumbnails":
            files = old_thumbnails()
            size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
            detail = f"Not looked at in {THUMBNAIL_DAYS} days" if files else "Nothing to clean"
        else:
            size, detail = SCANS[item]()
        out.append({"id": item, "title": title, "bytes": size, "size": human(size) if size else "",
                    "detail": detail, "root": root})
    return out


# ---------------------------------------------------------------- running

def clean_root(ids):
    """The system parts. Runs as root (pkexec lennox-cleanup root ...)."""
    if "packages" in ids and shutil.which("paccache"):
        _run(["paccache", "-rk2"], timeout=300)
        _run(["paccache", "-ruk0"], timeout=300)
    if "orphans" in ids:
        names = orphans()
        if names:
            _run(["pacman", "-Rns", "--noconfirm", *names], timeout=600)
    if "journal" in ids and shutil.which("journalctl"):
        _run(["journalctl", f"--vacuum-size={JOURNAL_KEEP}"], timeout=120)


def clean_user(ids, settings):
    if "trash" in ids:
        clean_trash(settings["cleanup"]["trash_days"])
    if "thumbnails" in ids:
        for path in old_thumbnails():
            _remove(path)
    if "aur" in ids:
        clean_aur()
    if "flatpak" in ids:
        clean_flatpak()


def _free():
    """Free bytes on the disks holding / and your home (counted once each)."""
    seen, total = set(), 0
    for path in ("/", HOME):
        try:
            dev = os.stat(path).st_dev
        except OSError:
            continue
        if dev not in seen:
            seen.add(dev)
            total += shutil.disk_usage(path).free
    return total


def _save_last(freed, auto):
    os.makedirs(os.path.dirname(LAST), exist_ok=True)
    with open(LAST + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"time": int(time.time()), "freed": freed, "auto": auto}, f)
    os.replace(LAST + ".tmp", LAST)


def last_run():
    try:
        with open(LAST, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clean(ids, settings, auto=False):
    """Clean `ids`; returns (bytes freed, system parts done or None if the password was refused)."""
    before = _free()
    root_ids = [i for i in ids if i in ROOT_IDS]
    root_ok = True
    if root_ids:
        tool = os.path.join(HOME, ".local", "bin", "lennox-cleanup")
        code, _, _ = _run(["pkexec", tool, "root", *root_ids], timeout=1200)
        root_ok = code == 0
    clean_user([i for i in ids if i not in ROOT_IDS], settings)
    freed = max(0, _free() - before)
    _save_last(freed, auto)
    return freed, root_ok


def _notify(title, body):
    _run(["notify-send", "-a", "Lennox", "-i", "user-trash-full", title, body])


def main(argv):
    mode = argv[1] if len(argv) > 1 else "scan"
    if mode == "root":
        if os.geteuid() != 0:
            print("lennox-cleanup root: run through pkexec", file=sys.stderr)
            return 1
        clean_root([i for i in argv[2:] if i in ROOT_IDS])
        return 0
    settings = S.load()
    if mode == "scan":
        items = scan(settings=settings)
        if "--json" in argv:
            print(json.dumps(items))
        else:
            for it in items:
                print(f"{it['title']:<26} {it['size'] or '-':>10}  {it['detail']}")
            print(f"{'Total':<26} {human(sum(it['bytes'] for it in items)):>10}")
        return 0
    if mode == "now":
        ids = [i for i in argv[2:] if i in ITEMS] or list(ITEMS)
        freed, root_ok = clean(ids, settings)
        message = f"Freed {human(freed)}" + ("" if root_ok else " (system parts skipped: no password)")
        print(message)
        if "--notify" in argv:
            _notify("Cleanup done", message)
        return 0
    if mode == "auto":
        if not settings["cleanup"]["weekly"]:
            return 0
        ids = [i for i in ITEMS if not ITEMS[i][1] and i != "flatpak"]
        freed, _ = clean(ids, settings, auto=True)
        if freed >= 50 * 1024 ** 2:
            _notify("Weekly cleanup", f"Freed {human(freed)}. Lennox Settings > Cleanup can free more.")
        return 0
    print("usage: lennox-cleanup scan [--json] | now [IDS...] [--notify] | auto", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
