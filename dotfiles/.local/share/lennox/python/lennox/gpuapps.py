"""Run chosen apps on the NVIDIA GPU, every time, however you open them (launcher, dock, file manager).

    python3 -m lennox.gpuapps list [--pinned]     the apps (a star marks the ones on the GTX)
    python3 -m lennox.gpuapps pin APP             APP is a desktop entry id: "blender" or "blender.desktop"
    python3 -m lennox.gpuapps unpin APP

Pinning writes a copy of the app's menu entry into ~/.local/share/applications whose command starts with
`lennox-gpu run`. Unpinning removes the copy (or puts back the entry you had). The NVIDIA chip sleeps whenever
no pinned app is open, so the battery only pays while the app runs.
"""

import os
import shutil
import sys

from . import settings as S

HOME = os.path.expanduser("~")
USER_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local", "share")), "applications")
SYSTEM_DIRS = ["/usr/share/applications", "/var/lib/flatpak/exports/share/applications",
               os.path.join(HOME, ".local", "share", "flatpak", "exports", "share", "applications")]
ORIG_DIR = os.path.join(S.STATE_DIR, "gpu-orig")
MARK = "X-Lennox-Gpu=true"
PREFIX = "lennox-gpu run "


def entry_id(name):
    name = os.path.basename(name)
    return name if name.endswith(".desktop") else name + ".desktop"


def parse(path):
    """{Name, Exec, hidden} from the [Desktop Entry] group (None if it is not an app)."""
    info, in_main = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_main = line == "[Desktop Entry]"
                elif in_main and "=" in line:
                    key, _, value = line.partition("=")
                    info.setdefault(key, value)
    except OSError:
        return None
    if info.get("Type", "Application") != "Application" or not info.get("Exec"):
        return None
    return {"name": info.get("Name", os.path.basename(path)), "exec": info["Exec"],
            "hidden": info.get("NoDisplay") == "true" or info.get("Hidden") == "true"}


def find_entry(app, dirs=None, user_dir=None):
    """The best file for an app id: your own copy first, then the system's."""
    app = entry_id(app)
    for d in [user_dir or USER_DIR] + list(dirs or SYSTEM_DIRS):
        path = os.path.join(d, app)
        if os.path.isfile(path):
            return path
    return None


def is_pinned(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return MARK in f.read()
    except OSError:
        return False


def apps(dirs=None, user_dir=None):
    """[{id, name, pinned}] every visible app, sorted by name."""
    user_dir = user_dir or USER_DIR
    seen = {}
    for d in list(dirs or SYSTEM_DIRS) + [user_dir]:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.endswith(".desktop"):
                seen[n] = os.path.join(d, n)
    out = []
    for n, path in seen.items():
        info = parse(path)
        if info and not info["hidden"]:
            out.append({"id": n, "name": info["name"], "pinned": is_pinned(os.path.join(user_dir, n))})
    return sorted(out, key=lambda a: a["name"].lower())


def rewrite(text):
    """Every Exec= line (the app and its actions) starts with the GPU launcher; the marker goes in the main group."""
    out, done = [], False
    for line in text.splitlines():
        if line.startswith("Exec=") and not line[5:].startswith(PREFIX):
            line = "Exec=" + PREFIX + line[5:]
        out.append(line)
        if line.strip() == "[Desktop Entry]" and not done:
            out.append(MARK)
            done = True
    return "\n".join(out) + "\n"


def pin(app, dirs=None, user_dir=None, orig_dir=None):
    """Returns (ok, message)."""
    user_dir, orig_dir = user_dir or USER_DIR, orig_dir or ORIG_DIR
    app = entry_id(app)
    src = find_entry(app, dirs, user_dir)
    if not src:
        return False, f"No app called {app}. `lennox-gpu apps` lists them."
    if is_pinned(src):
        return True, f"{app} already runs on the NVIDIA GPU."
    target = os.path.join(user_dir, app)
    if src == target:                      # your own entry: keep it safe so unpin can bring it back
        os.makedirs(orig_dir, exist_ok=True)
        shutil.copy2(src, os.path.join(orig_dir, app))
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    os.makedirs(user_dir, exist_ok=True)
    with open(target + ".tmp", "w", encoding="utf-8") as f:
        f.write(rewrite(text))
    os.replace(target + ".tmp", target)
    return True, f"{app} now runs on the NVIDIA GPU."


def unpin(app, user_dir=None, orig_dir=None):
    user_dir, orig_dir = user_dir or USER_DIR, orig_dir or ORIG_DIR
    app = entry_id(app)
    target = os.path.join(user_dir, app)
    if not is_pinned(target):
        return False, f"{app} is not pinned."
    saved = os.path.join(orig_dir, app)
    if os.path.isfile(saved):
        shutil.move(saved, target)
    else:
        os.remove(target)
    return True, f"{app} is back on the Intel GPU."


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        for a in apps():
            if "--pinned" in argv and not a["pinned"]:
                continue
            print(f"{'*' if a['pinned'] else ' '} {a['id'][:-8]:<40} {a['name']}")
        return 0
    if cmd in ("pin", "unpin") and len(argv) > 2:
        ok, msg = (pin if cmd == "pin" else unpin)(argv[2])
        print(msg)
        return 0 if ok else 1
    print("usage: lennox-gpu apps [--pinned] | pin APP | unpin APP", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
