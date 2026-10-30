"""Settings backup: your Lennox setup in one small file, restored in one step.

    python3 -m lennox.backup now [FOLDER]     back up (to the folder in Settings > Backup)
    python3 -m lennox.backup auto             the weekly run (only when it's on)
    python3 -m lennox.backup list [--json]    backups in the folder, newest first
    python3 -m lennox.backup restore FILE     put a backup back (then everything is re-applied)

What's in it: Lennox settings, your tweaks (custom.lua, monitors, kitty, zsh),
Claude Code rules, alarms and timers, focus and sleep stats, and the current
wallpaper. Pick a folder that survives a reinstall: the Windows drive, a USB
stick, or a synced cloud folder.
"""

import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import time

from . import VERSION
from . import settings as S

HOME = os.path.expanduser("~")
# Paths in your home that are saved (when they exist)
FILES = [
    ".config/lennox/settings.json",
    ".config/hypr/custom.lua",
    ".config/hypr/monitors.lua",
    ".config/hypr/workspaces.lua",
    ".config/kitty/custom.conf",
    ".config/zshrc/90-custom",
    ".claude/CLAUDE.md",
    ".local/state/lennox/clock.json",
    ".local/state/lennox/focus_log.json",
    ".local/state/lennox/sleep.log",
]
WALLPAPER_NOTE = ".cache/lennox/wallpaper/current"   # the path of the current wallpaper (lennox-wallpaper)
WALLPAPER_DIR = ".config/lennox/wallpapers/restored"
PREFIX = "lennox-backup-"
MANIFEST = "lennox-backup.json"


def folder(settings=None):
    settings = settings or S.load()
    return os.path.expanduser(settings["backup"]["folder"] or "")


def _wallpaper():
    try:
        with open(os.path.join(HOME, WALLPAPER_NOTE), encoding="utf-8") as f:
            path = f.read().strip()
    except OSError:
        return None
    return path if path and os.path.isfile(path) and os.path.getsize(path) < 40 * 1024 ** 2 else None


def create(dest, now=None):
    """Writes a backup into `dest`; returns its path."""
    now = time.time() if now is None else now
    os.makedirs(dest, exist_ok=True)
    name = PREFIX + time.strftime("%Y-%m-%d-%H%M%S", time.localtime(now)) + ".tar.gz"
    path = os.path.join(dest, name)
    saved = [rel for rel in FILES if os.path.isfile(os.path.join(HOME, rel))]
    wallpaper = _wallpaper()
    manifest = {"version": VERSION, "time": int(now), "computer": socket.gethostname(), "files": saved,
                "wallpaper": os.path.basename(wallpaper) if wallpaper else None}
    tmp = path + ".part"
    with tarfile.open(tmp, "w:gz") as tar:
        data = json.dumps(manifest, indent=1).encode()
        info = tarfile.TarInfo(MANIFEST)
        info.size, info.mtime = len(data), int(now)
        tar.addfile(info, io.BytesIO(data))
        for rel in saved:
            tar.add(os.path.join(HOME, rel), arcname="home/" + rel, recursive=False)
        if wallpaper:
            tar.add(wallpaper, arcname="wallpaper/" + os.path.basename(wallpaper), recursive=False)
    os.replace(tmp, path)
    return path


def backups(dest):
    """[(path, manifest)] newest first; unreadable files are skipped."""
    try:
        names = sorted((n for n in os.listdir(dest) if n.startswith(PREFIX) and n.endswith(".tar.gz")),
                       reverse=True)
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(dest, name)
        try:
            with tarfile.open(path, "r:gz") as tar:
                manifest = json.load(tar.extractfile(MANIFEST))
        except (OSError, tarfile.TarError, KeyError, ValueError, AttributeError):
            continue
        out.append((path, manifest))
    return out


def prune(dest, keep):
    for path, _ in backups(dest)[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass


def restore(path, home=HOME):
    """Puts the files back. Only the known paths are ever written: a backup
    can't place anything else in your home."""
    allowed = {"home/" + rel: rel for rel in FILES}
    restored, wallpaper = [], None
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            if member.name in allowed:
                target = os.path.join(home, allowed[member.name])
            elif member.name.startswith("wallpaper/") and "/" not in member.name[len("wallpaper/"):] \
                    and not member.name.endswith(("/", "..")):
                target = os.path.join(home, WALLPAPER_DIR, os.path.basename(member.name))
                wallpaper = target
            else:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            source = tar.extractfile(member)
            with open(target + ".restore", "wb") as f:
                f.write(source.read())
            os.replace(target + ".restore", target)
            restored.append(target)
    if wallpaper:
        # So `lennox-wallpaper --restore` (login, the installer) puts it back
        note = os.path.join(home, WALLPAPER_NOTE)
        os.makedirs(os.path.dirname(note), exist_ok=True)
        with open(note, "w", encoding="utf-8") as f:
            f.write(wallpaper + "\n")
    return restored, wallpaper


def _bin(name):
    return os.path.join(HOME, ".local", "bin", name)


def _notify(title, body, icon="document-save-symbolic"):
    subprocess.run(["notify-send", "-a", "Lennox", "-i", icon, title, body], capture_output=True, check=False)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "list"
    settings = S.load()
    if mode in ("now", "auto"):
        if mode == "auto" and not settings["backup"]["weekly"]:
            return 0
        dest = os.path.expanduser(argv[2]) if mode == "now" and len(argv) > 2 else folder(settings)
        if not dest:
            print("Choose a backup folder first (Lennox Settings > Backup)", file=sys.stderr)
            return 1
        if not os.path.isdir(os.path.dirname(dest.rstrip("/")) or "/"):
            # e.g. the Windows drive or USB stick isn't plugged in / mounted
            if mode == "auto":
                _notify("Backup skipped", f"{dest} isn't there (drive not connected?)", "dialog-warning-symbolic")
            print(f"{dest} isn't there (drive not connected?)", file=sys.stderr)
            return 1
        try:
            path = create(dest)
        except OSError as e:
            print(f"Backup failed: {e}", file=sys.stderr)
            if mode == "auto":
                _notify("Backup failed", str(e), "dialog-error-symbolic")
            return 1
        prune(dest, settings["backup"]["keep"])
        print(path)
        return 0
    if mode == "list":
        found = backups(folder(settings))
        if "--json" in argv:
            print(json.dumps([{"path": p, **m} for p, m in found]))
        else:
            for p, m in found:
                print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(m['time']))}  "
                      f"Lennox {m['version']}  {m.get('computer', '')}  {p}")
        return 0
    if mode == "restore" and len(argv) > 2:
        try:
            restored, wallpaper = restore(os.path.expanduser(argv[2]))
        except (OSError, tarfile.TarError) as e:
            print(f"Couldn't restore: {e}", file=sys.stderr)
            return 1
        print(f"Restored {len(restored)} files")
        if "--no-apply" not in argv:
            subprocess.run([_bin("lennox-apply"), "all"], capture_output=True, check=False)
            if wallpaper:
                subprocess.run([_bin("lennox-wallpaper"), "--restore", "--quiet"], capture_output=True, check=False)
        return 0
    print("usage: lennox-backup now [FOLDER] | auto | list [--json] | restore FILE [--no-apply]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
