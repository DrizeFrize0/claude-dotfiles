"""Tidy downloads: new files in ~/Downloads go into folders by kind, and every move can be undone.

    python3 -m lennox.tidy run [--dry]     sort what is there now
    python3 -m lennox.tidy undo            put the last batch back
    python3 -m lennox.tidy status

Only loose files at the top of the Downloads folder are touched, only once they have been there for a minute (so
nothing is moved while it is still downloading), and only into folders inside Downloads.
"""

import json
import os
import shutil
import sys
import time

from . import settings as S

LOG = os.path.join(S.STATE_DIR, "tidy-log.json")
PARTIAL = (".crdownload", ".part", ".opdownload", ".download", ".tmp", ".partial")
KINDS = {
    "Images": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic", ".avif"),
    "Documents": (".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".epub", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".rtf"),
    "Archives": (".zip", ".rar", ".7z", ".tar", ".gz", ".xz", ".bz2", ".zst", ".tgz"),
    "Installers": (".appimage", ".deb", ".rpm", ".exe", ".msi", ".dmg", ".pkg", ".run", ".flatpakref"),
    "Videos": (".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv"),
    "Audio": (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus"),
    "Minecraft": (".jar", ".mrpack", ".mcpack", ".litemod"),
    "Code": (".py", ".js", ".ts", ".json", ".sh", ".lua", ".html", ".css", ".c", ".cpp", ".java", ".rs", ".go"),
}
FOLDERS = tuple(KINDS)


def kind_of(name):
    lower = name.lower()
    if lower.endswith((".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst")):
        return "Archives"
    ext = os.path.splitext(lower)[1]
    for kind, exts in KINDS.items():
        if ext in exts:
            return kind
    return None                                      # unknown kinds stay where they are


def downloads_dir():
    return os.path.expanduser("~/Downloads")


def plan(folder, now, wait):
    """[(from, to)] for the loose files that are done downloading and have a kind."""
    moves = []
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return moves
    for e in entries:
        if e.name.startswith(".") or not e.is_file(follow_symlinks=False) or e.name.endswith(PARTIAL):
            continue
        kind = kind_of(e.name)
        try:
            age = now - e.stat().st_mtime
        except OSError:
            continue
        if kind and age >= wait:
            moves.append((e.path, os.path.join(folder, kind, e.name)))
    return moves


def free_name(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base} ({n}){ext}"):
        n += 1
    return f"{base} ({n}){ext}"


def _log(path=None):
    try:
        with open(path or LOG, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def run(folder=None, now=None, wait=None, dry=False, log_path=None):
    folder = folder or downloads_dir()
    now = time.time() if now is None else now
    wait = S.load()["tidy"]["wait_seconds"] if wait is None else wait
    moves = plan(folder, now, wait)
    done = []
    for src, dst in moves:
        if dry:
            done.append((src, dst))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        dst = free_name(dst)
        try:
            shutil.move(src, dst)
        except OSError:
            continue
        done.append((src, dst))
    if done and not dry:
        batch = [{"from": a, "to": b, "time": now} for a, b in done]
        os.makedirs(os.path.dirname(log_path or LOG), exist_ok=True)
        with open(log_path or LOG, "w", encoding="utf-8") as f:
            json.dump(_log(log_path) + batch, f)
    return done


def undo(log_path=None):
    """Puts the most recent batch (everything moved in the same run) back where it was."""
    path = log_path or LOG
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return []
    if not entries:
        return []
    last = entries[-1]["time"]
    batch = [e for e in entries if abs(e["time"] - last) < 1]
    rest = [e for e in entries if e not in batch]
    back = []
    for e in reversed(batch):
        if os.path.exists(e["to"]):
            target = free_name(e["from"])
            try:
                shutil.move(e["to"], target)
                back.append((e["to"], target))
            except OSError:
                rest.append(e)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rest, f)
    return back


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    if mode == "run":
        done = run(dry="--dry" in argv, wait=0 if "--now" in argv else None)
        for a, b in done:
            print(("would move " if "--dry" in argv else "moved ") + os.path.basename(a) + "  ->  " + os.path.relpath(b, downloads_dir()))
        print(f"{len(done)} file(s)." if done else "Nothing to sort.")
    elif mode == "undo":
        back = undo()
        print(f"{len(back)} file(s) put back." if back else "Nothing to undo.")
    elif mode == "status":
        print("on" if S.load()["tidy"]["on"] else "off", "·", downloads_dir(), "·", len(plan(downloads_dir(), time.time(), 0)), "file(s) would be sorted")
    else:
        print("usage: lennox-tidy run [--dry] [--now] | undo | status", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
