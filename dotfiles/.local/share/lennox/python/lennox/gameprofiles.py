"""Per-game settings: each game gets its own performance mode, notifications and
night light while it's open, and everything goes back when it closes.

    python3 -m lennox.gameprofiles watch      (started at login) follows Hyprland's events
    python3 -m lennox.gameprofiles check      apply / undo once, now
    python3 -m lennox.gameprofiles list       the profiles as JSON
    python3 -m lennox.gameprofiles add NAME [MATCH]
    python3 -m lennox.gameprofiles remove MATCH

A profile matches a window whose class or title contains its `match` text
(lower case). Lennox Settings > Game Center edits them.
"""

import fcntl
import json
import os
import select
import socket
import subprocess
import sys
import time

from . import settings as S
from . import sh

PROFILES = os.path.join(S.CONFIG_DIR, "game-profiles.json")
STATE = os.path.join(S.RUNTIME_DIR, "gameprofile.json")
LOCK = os.path.join(S.RUNTIME_DIR, "gameprofile-watch.lock")
PERF_MODES = ("", "quiet", "balanced", "max")
DEFAULT = {"perf": "max", "dnd": True, "nightlight_off": True}
SETTLE = 0.8                     # events come in bursts: wait for the dust to settle


# ---------------------------------------------------------------- profiles

def clean(profile):
    """A profile as stored: only known keys, valid values (None if it has no match text)."""
    match = str(profile.get("match", "")).strip().lower()
    if not match:
        return None
    perf = profile.get("perf", DEFAULT["perf"])
    return {"match": match, "name": str(profile.get("name") or match)[:60],
            "perf": perf if perf in PERF_MODES else DEFAULT["perf"],
            "dnd": bool(profile.get("dnd", DEFAULT["dnd"])),
            "nightlight_off": bool(profile.get("nightlight_off", DEFAULT["nightlight_off"]))}


def load(path=PROFILES):
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f).get("profiles", [])
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for p in raw if isinstance(raw, list) else []:
        c = clean(p) if isinstance(p, dict) else None
        if c and all(c["match"] != o["match"] for o in out):
            out.append(c)
    return out


def save(profiles, path=PROFILES):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"profiles": profiles}, f, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def add(profiles, name, match=None):
    """Adds a profile (the match text defaults to the name). Returns the new list."""
    profile = clean({"name": name, "match": match or name})
    if profile is None or any(p["match"] == profile["match"] for p in profiles):
        return profiles
    return profiles + [profile]


def match_client(clients, profiles):
    """The first profile that fits an open window: (profile, client) or None."""
    for client in clients:
        if not client.get("mapped", True):
            continue
        hay = " ".join([client.get("class") or "", client.get("initialClass") or "",
                        client.get("title") or ""]).lower()
        for profile in profiles:
            if profile["match"] in hay:
                return profile, client
    return None


# ---------------------------------------------------------------- game mode by itself

# Window classes (lower case, "starts with" or "contains") that mean "this is a game"
GAME_START = ("steam_app_", "gamescope", "minecraft", "net.minecraft", "com.mojang", "lunarclient", "lunar client",
              "badlion", "cs2", "dota2", "hl2_linux", "csgo", "factorio", "terraria", "stardew", "hollow knight",
              "eldenring", "valheim", "among us", "roblox", "osu", "supertuxkart", "xonotic", "openttd", "mgba", "dolphin-emu", "retroarch", "yuzu", "ryujinx", "rpcs3", "pcsx2", "ppsspp", "duckstation")
GAME_TITLE = ("minecraft",)            # Prism / MultiMC run Minecraft in a Java window with this title


def is_game_client(client, extra=()):
    """True for a window that is a game: Steam/Proton games, gamescope, Minecraft, emulators, or your own words."""
    if not client.get("mapped", True):
        return False
    names = [(client.get("class") or "").lower(), (client.get("initialClass") or "").lower()]
    title = (client.get("title") or "").lower()
    if any(n.startswith(GAME_START) for n in names if n):
        return True
    if any(t in title for t in GAME_TITLE) and any(n.startswith(("java", "minecraft", "org.prismlauncher", "net.minecraft")) or n.endswith("-game") for n in names if n):
        return True
    return any(w and (w in names[0] or w in names[1] or w in title) for w in extra)


def auto_action(we_turned_it_on, mode_on, game_open):
    """'on' to start game mode, 'off' to end it (only if we started it), or None."""
    if game_open and not mode_on:
        return "on"
    if not game_open and we_turned_it_on and mode_on:
        return "off"
    return None


def _auto_flag():
    return os.path.join(S.RUNTIME_DIR, "autogame")


def auto_game(clients, settings, when):
    """Game mode follows the games. `when` is 'before' (turn on, before the per-game profile) or
    'after' (turn off, after the profile went back): that order puts every setting back as it was."""
    if not settings["games"]["auto_mode"]:
        if os.path.exists(_auto_flag()):                       # switched off in Settings while it was on
            _set_game_mode("off")
        return
    extra = [w.strip().lower() for w in settings["games"]["auto_extra"].split(",") if w.strip()]
    game_open = any(is_game_client(c, extra) for c in clients)
    mode_on = _out([_bin("lennox-mode"), "game", "status"]) == "on"
    action = auto_action(os.path.exists(_auto_flag()), mode_on, game_open)
    if action == "on" and when == "before":
        _set_game_mode("on")
    elif action == "off" and when == "after":
        _set_game_mode("off")


def _set_game_mode(state):
    subprocess.run([_bin("lennox-mode"), "game", state], capture_output=True, check=False)
    if state == "on":
        os.makedirs(os.path.dirname(_auto_flag()), exist_ok=True)
        open(_auto_flag(), "w").close()                        # noqa: SIM115  an empty marker file
    else:
        try:
            os.remove(_auto_flag())
        except OSError:
            pass


# ---------------------------------------------------------------- doing it

_out, _bin = sh.out, sh.bin_path


def _read_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_state(state):
    if state is None:
        try:
            os.remove(STATE)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(STATE + ".tmp", STATE)


def apply(profile):
    """Switches to the profile, remembering what to go back to."""
    prev = {}
    if profile["perf"]:
        prev["perf"] = _out([_bin("lennox-perf"), "status"])
        subprocess.run([_bin("lennox-perf"), profile["perf"]], capture_output=True, check=False)
    if profile["dnd"]:
        prev["dnd"] = _out(["swaync-client", "-D"]) == "true"
        subprocess.run(["swaync-client", "--dnd-on", "--skip-wait"], capture_output=True, check=False)
    if profile["nightlight_off"]:
        prev["night"] = _out([_bin("lennox-nightlight"), "status"])
        if prev["night"] == "on":
            subprocess.run([_bin("lennox-nightlight"), "off"], capture_output=True, check=False)
    _write_state({"match": profile["match"], "name": profile["name"], "prev": prev})
    subprocess.run([_bin("lennox-widgets"), "island", "event", "input-gaming-symbolic",
                    f"{profile['name']} profile", "3"], capture_output=True, check=False)


def undo(state):
    prev = state.get("prev", {})
    if prev.get("perf") in PERF_MODES[1:]:
        subprocess.run([_bin("lennox-perf"), prev["perf"]], capture_output=True, check=False)
    if prev.get("dnd") is False:
        subprocess.run(["swaync-client", "--dnd-off", "--skip-wait"], capture_output=True, check=False)
    if prev.get("night") == "on":
        subprocess.run([_bin("lennox-nightlight"), "on"], capture_output=True, check=False)
    _write_state(None)


def decide(state, found):
    """What to do now: 'apply' (with the profile), 'undo', 'switch' (undo then apply) or None."""
    if found is None:
        return "undo" if state else None
    if state is None:
        return "apply"
    return None if state.get("match") == found[0]["match"] else "switch"


def check():
    settings = S.load()
    try:
        clients = json.loads(_out(["hyprctl", "clients", "-j"]) or "[]")
    except ValueError:
        return None
    if not settings["games"]["profiles"]:
        state = _read_state()
        if state:
            undo(state)
        auto_game(clients, settings, "before")
        auto_game(clients, settings, "after")
        return None
    found = match_client(clients, load())
    state = _read_state()
    action = decide(state, found)
    if action in ("undo", "switch"):
        undo(state)
    auto_game(clients, settings, "before")                     # game mode first: it remembers your real power mode
    if action in ("apply", "switch"):
        apply(found[0])
    auto_game(clients, settings, "after")
    return action


# ---------------------------------------------------------------- watching Hyprland

def _instance_dir():
    base = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "hypr")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if sig:
        return os.path.join(base, sig)
    try:
        dirs = [os.path.join(base, d) for d in os.listdir(base)]
    except OSError:
        return None
    dirs = [d for d in dirs if os.path.exists(os.path.join(d, ".socket2.sock"))]
    return max(dirs, key=os.path.getmtime) if dirs else None


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")  # noqa: SIM115  held for the life of the process
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    wanted = (b"openwindow>>", b"closewindow>>", b"windowtitle>>", b"windowtitlev2>>")
    while True:
        hypr = _instance_dir()
        if not hypr or not os.path.exists(os.path.join(hypr, ".socket2.sock")):
            return 0                                     # Hyprland is gone: logged out
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as events:
                events.connect(os.path.join(hypr, ".socket2.sock"))
                check()
                pending, buffer = None, b""
                while True:
                    timeout = 30 if pending is None else max(0.05, pending - time.time())
                    ready, _, _ = select.select([events], [], [], timeout)
                    if ready:
                        chunk = events.recv(65536)
                        if not chunk:
                            break
                        buffer += chunk
                        *lines, buffer = buffer.split(b"\n")
                        if any(line.startswith(wanted) for line in lines):
                            pending = time.time() + SETTLE
                    elif pending is not None or timeout == 30:
                        pending = None
                        check()                          # after a burst, and every 30 s as a safety net
        except OSError:
            pass
        time.sleep(2)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "list"
    if mode == "watch":
        return watch()
    if mode == "check":
        print(check() or "nothing to do")
    elif mode == "list":
        print(json.dumps(load(), ensure_ascii=False))
    elif mode == "add" and len(argv) > 2:
        save(add(load(), argv[2], argv[3] if len(argv) > 3 else None))
    elif mode == "remove" and len(argv) > 2:
        save([p for p in load() if p["match"] != argv[2].lower()])
    else:
        print("usage: lennox-gameprofile watch | check | list | add NAME [MATCH] | remove MATCH", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
