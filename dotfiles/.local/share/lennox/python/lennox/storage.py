"""Storage view: what is using the disk, biggest first, with a safe way to clear it.

    python3 -m lennox.storage scan [FOLDER]      JSON: free space and the biggest items in FOLDER (default: home)
    python3 -m lennox.storage trash PATH         move to the trash (never a delete)
    python3 -m lennox.storage open PATH          show it in the file manager

Only things inside your home folder can be trashed, and never the home folder
itself or the folders Lennox and your session need.
"""

import json
import os
import shutil
import subprocess
import sys

from . import sh

HOME = os.path.expanduser("~")
# Top level folders in home that are never offered for the trash
PROTECTED = {".config", ".local", ".ssh", ".gnupg", ".cache", ".var", ".mozilla"}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def tree_size(path, limit=2_000_000):
    """Bytes under path (does not follow links, counts at most `limit` files)."""
    total, seen = 0, 0
    stack = [path]
    while stack and seen < limit:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    seen += 1
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_blocks * 512
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def scan(folder=HOME, top=14):
    folder = os.path.realpath(folder)
    items = []
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_symlink():
                    continue
                try:
                    size = tree_size(e.path) if e.is_dir(follow_symlinks=False) else e.stat(follow_symlinks=False).st_blocks * 512
                except OSError:
                    continue
                items.append({"name": e.name, "path": e.path, "size": size, "dir": e.is_dir(follow_symlinks=False),
                              "safe": can_trash(e.path)})
    except OSError:
        pass
    items.sort(key=lambda x: -x["size"])
    usage = shutil.disk_usage(folder)
    return {"folder": folder, "total": usage.total, "free": usage.free, "used": usage.used,
            "items": items[:top], "listed": sum(x["size"] for x in items)}


def can_trash(path):
    """True for something inside home that is not home itself or a protected folder."""
    real = os.path.realpath(path)
    if not real.startswith(HOME + os.sep) or real == HOME:
        return False
    top = real[len(HOME) + 1:].split(os.sep)[0]
    return top not in PROTECTED


def trash(path):
    if not can_trash(path):
        print(f"Not allowed: {path}", file=sys.stderr)
        return 1
    if not os.path.lexists(path):
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    code, _out, err = sh.run(["gio", "trash", "--", path], 120)
    if code != 0:
        print(err.strip() or "Couldn't move it to the trash", file=sys.stderr)
    return code


def main(argv):
    mode = argv[1] if len(argv) > 1 else "scan"
    arg = argv[2] if len(argv) > 2 else None
    if mode == "scan":
        print(json.dumps(scan(arg or HOME)))
    elif mode == "trash" and arg:
        return trash(arg)
    elif mode == "open" and arg:
        subprocess.Popen(["xdg-open", arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        print("usage: lennox-storage scan [FOLDER] | trash PATH | open PATH", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
