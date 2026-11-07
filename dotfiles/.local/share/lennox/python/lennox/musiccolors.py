"""Colors from your music: the desktop colors follow the cover of the song that is playing.

    python3 -m lennox.musiccolors start|stop|sync|run

While music plays, the cover is used as the color source (the wallpaper, the lock screen and the login screen stay as
they are). A minute and a half after the music stops, the colors from your wallpaper come back. It changes at most
every 25 seconds, and never while paused. Settings > Extras turns it on.
"""

import os
import signal
import subprocess
import sys
import time

from . import settings as S
from . import sh

MIN_GAP = 25.0            # seconds between color changes: each one reloads the desktop's colors
RESTORE_AFTER = 90.0      # seconds without music before the wallpaper's colors return
EVERY = 8                 # seconds between looks
PIDFILE = os.path.join(S.RUNTIME_DIR, "musiccolors.pid")


def decide(state, art, status, now):
    """What to do now: 'theme' (use this cover), 'restore' (back to the wallpaper's colors) or None.
    `state` is {'art', 'themed_at', 'playing_at', 'themed'} and is updated in place."""
    if status == "Playing":
        state["playing_at"] = now
        if art and art != state.get("art") and now - state.get("themed_at", 0) >= MIN_GAP:
            state.update(art=art, themed_at=now, themed=True)
            return "theme"
        return None
    if status == "Paused":
        state["playing_at"] = now                                    # a pause is not the end of the music
        return None
    if state.get("themed") and now - state.get("playing_at", now) >= RESTORE_AFTER:
        state.update(art=None, themed=False)
        return "restore"
    return None


def look():
    """(status, local cover file or None) of the player that is playing, via playerctl."""
    status = sh.out(["playerctl", "status"], 3)
    if status != "Playing":
        return status, None
    from .widgets import data
    return status, data.art_file(sh.out(["playerctl", "metadata", "mpris:artUrl"], 3))


def apply(action, art=None):
    wallpaper = sh.bin_path("lennox-wallpaper")
    if action == "theme" and art:
        env = dict(os.environ, LENNOX_COLORS_ONLY="1")
        subprocess.run([wallpaper, art, "--theme-only", "--quiet"], env=env, capture_output=True, check=False, timeout=120)
    elif action == "restore":
        subprocess.run([wallpaper, "--restore", "--theme-only", "--quiet"], capture_output=True, check=False, timeout=120)


def run():
    os.makedirs(os.path.dirname(PIDFILE), exist_ok=True)
    with open(PIDFILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_a: sys.exit(0))
    state = {}
    while True:
        try:
            if not S.load()["musiccolors"]["on"]:
                return 0
            status, art = look()
            action = decide(state, art, status, time.time())
            if action:
                apply(action, art)
        except Exception:  # noqa: BLE001  a flaky player must not stop the watcher
            pass
        time.sleep(EVERY)


def running():
    try:
        with open(PIDFILE, encoding="utf-8") as f:
            pid = int(f.read())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def main(argv):
    mode = argv[1] if len(argv) > 1 else "sync"
    if mode == "run":
        return run()
    if mode == "stop" or (mode == "sync" and not S.load()["musiccolors"]["on"]):
        pid = running()
        if pid:
            os.kill(pid, signal.SIGTERM)
        return 0
    if mode in ("start", "sync"):
        if not running():
            subprocess.Popen([sys.executable, "-m", "lennox.musiccolors", "run"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return 0
    print("usage: lennox-musiccolors start | stop | sync", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
