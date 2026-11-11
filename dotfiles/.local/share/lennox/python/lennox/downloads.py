"""Downloads in the bar: progress of browser downloads, and a click opens the finished file.

    python3 -m lennox.downloads waybar     JSON for the bar item
    python3 -m lennox.downloads open       open the last finished download

Browsers write a download to a partial file (.crdownload, .part, .opdownload)
and rename it when done. The bar item counts those, shows how much has come in
so far, and for a minute after one finishes it shows its name.
"""

import json
import os
import subprocess
import sys
import time

from . import settings as S
from . import sh

STATE = os.path.join(S.RUNTIME_DIR, "downloads.json")
PARTIAL = (".crdownload", ".part", ".opdownload", ".download")
SHOW_DONE = 60


def folder(settings):
    return os.path.expanduser(settings["downloads"]["folder"] or "~/Downloads")


def partials(path):
    """{file: bytes so far} for the downloads in progress."""
    out = {}
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.name.endswith(PARTIAL) and e.is_file():
                    out[e.path] = e.stat().st_size
    except OSError:
        pass
    return out


def final_name(partial, path):
    for suffix in PARTIAL:
        if partial.endswith(suffix):
            candidate = partial[:-len(suffix)]
            if os.path.exists(candidate):
                return candidate
    # Some browsers pick another name: the newest ordinary file in the folder
    try:
        files = [e for e in os.scandir(path) if e.is_file() and not e.name.endswith(PARTIAL) and not e.name.startswith(".")]
    except OSError:
        return None
    return max(files, key=lambda e: e.stat().st_mtime).path if files else None


def step(state, now_parts, path, now):
    """Moves the state forward: returns (new state, [paths that just finished])."""
    finished = []
    for partial in state.get("partials", {}):
        if partial not in now_parts:
            done = final_name(partial, path)
            if done:
                finished.append(done)
    new = {"partials": now_parts, "last": finished[-1] if finished else state.get("last"),
           "last_time": now if finished else state.get("last_time", 0)}
    return new, finished


def size_text(n):
    return f"{n / 1e6:.0f} MB" if n >= 1e6 else f"{max(n // 1000, 1)} KB"


def bar(state, now):
    parts = state.get("partials", {})
    if parts:
        total = sum(parts.values())
        return {"text": f"󰇚 {len(parts)}  {size_text(total)}" if len(parts) > 1 else f"󰇚 {size_text(total)}",
                "class": "active", "tooltip": f"{len(parts)} download(s) in progress, {size_text(total)} so far"}
    if state.get("last") and now - state.get("last_time", 0) < SHOW_DONE:
        name = os.path.basename(state["last"])
        return {"text": f"󰄬 {name[:22]}{'…' if len(name) > 22 else ''}", "class": "done",
                "tooltip": f"Finished: {name}\nClick to open"}
    return {"text": ""}


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "waybar"
    settings = S.load()
    if mode == "waybar":
        if not settings["downloads"]["on"]:
            print(json.dumps({"text": ""}))
            return 0
        now, path = time.time(), folder(settings)
        state, finished = step(load_state(), partials(path), path, now)
        save_state(state)
        for done in finished:
            sh.notify("Download finished", os.path.basename(done), "folder-download-symbolic")
        print(json.dumps(bar(state, now), ensure_ascii=False))
    elif mode == "open":
        last = load_state().get("last")
        target = last if last and os.path.exists(last) else folder(settings)
        subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        print("usage: lennox-downloads waybar | open", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
