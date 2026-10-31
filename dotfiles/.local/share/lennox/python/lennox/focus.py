"""Focus mode: a timed session with distractions blocked, then a short break.

    python3 -m lennox.focus start [MINUTES]   start (default: Lennox Settings > Focus)
    python3 -m lennox.focus stop | toggle
    python3 -m lennox.focus more [MINUTES]    add time (default 5)
    python3 -m lennox.focus skip              skip the break (the next round starts now)
    python3 -m lennox.focus status            JSON (the island and the quick panel read it)
    python3 -m lennox.focus stats             JSON: today, this week, streak
    python3 -m lennox.focus run               (started by `start`) the watcher

While focusing: chosen apps close when they open (Discord, Steam…), chosen
sites don't load (blocked in /etc/hosts), notifications wait in the panel,
and the island counts down. At the end: a sound, then a break.
"""

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time

from . import settings as S

STATE = os.path.join(S.STATE_DIR, "focus.json")
LOG = os.path.join(S.STATE_DIR, "focus_log.json")
RUN_LOCK = os.path.join(S.RUNTIME_DIR, "focus-run.lock")
HOSTS_TOOL = os.environ.get("LENNOX_FOCUS_HOSTS_TOOL", "/usr/local/bin/lennox-focus-hosts")   # tests swap it
SOUND_END = "/usr/share/sounds/freedesktop/stereo/complete.oga"
SOUND_BREAK_OVER = "/usr/share/sounds/freedesktop/stereo/bell.oga"
# Never closed, whatever the list says: you need these to work
NEVER_BLOCK = {"kitty", "dev.lennox.settings", "dev.lennox.clock", "code", "org.gnome.nautilus"}
LOG_DAYS = 120


# ---------------------------------------------------------------- files

def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def load_state():
    state = _read(STATE, None)
    return state if isinstance(state, dict) and state.get("phase") in ("focus", "break") else None


def save_state(state):
    if state is None:
        try:
            os.remove(STATE)
        except OSError:
            pass
    else:
        _write(STATE, state)


def split_list(text):
    """'Discord, steam  youtube.com' -> ['discord', 'steam', 'youtube.com']"""
    return [w for w in re.split(r"[\s,;]+", (text or "").lower()) if w]


# ---------------------------------------------------------------- the pure part (tested)

def status(state, now):
    if not state:
        return {"active": False}
    left = max(0, int(round(state["end"] - now)))
    return {"active": True, "phase": state["phase"], "left": left, "end": state["end"],
            "minutes": state.get("minutes", 0), "start": state.get("start", now),
            "round": state.get("round", 1), "rounds": state.get("rounds", 1)}


def log_session(log, start, end):
    """Adds a focus session (only if it lasted a minute or more); keeps LOG_DAYS of history."""
    minutes = int((end - start) // 60)
    if minutes >= 1:
        log.append({"start": int(start), "minutes": minutes})
    cutoff = end - LOG_DAYS * 86400
    return [x for x in log if x.get("start", 0) >= cutoff]


def _day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def stats(log, now):
    today = _day(now)
    by_day = {}
    for x in log:
        by_day[_day(x["start"])] = by_day.get(_day(x["start"]), 0) + x["minutes"]
    streak, day = 0, now
    if today not in by_day:
        day -= 86400                    # today isn't over: the streak can still be yesterday's
    while _day(day) in by_day:
        streak += 1
        day -= 86400
    days = [{"day": _day(now - i * 86400), "minutes": by_day.get(_day(now - i * 86400), 0)}
            for i in range(6, -1, -1)]
    return {"today": by_day.get(today, 0),
            "sessions_today": sum(1 for x in log if _day(x["start"]) == today),
            "week": sum(d["minutes"] for d in days),     # the last 7 days, today included
            "streak": streak, "days": days}


def to_close(clients, blocked):
    """Windows of blocked apps: [(pid, name)]. Matches the app's class or first title."""
    out = []
    for c in clients:
        names = {(c.get("class") or "").lower(), (c.get("initialClass") or "").lower()}
        if names & NEVER_BLOCK:
            continue
        hay = " ".join(names) + " " + (c.get("initialTitle") or "").lower()
        for app in blocked:
            if app and app in hay:
                out.append((c.get("pid"), c.get("class") or app))
                break
    return out


# ---------------------------------------------------------------- doing things

def _quiet(argv, timeout=10):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _island(icon, text, seconds=4):
    _quiet([os.path.expanduser("~/.local/bin/lennox-widgets"), "island", "event", icon, text, str(seconds)], 3)


def _notify(title, body, icon="emblem-ok-symbolic"):
    _quiet(["notify-send", "-a", "Lennox", "-i", icon, title, body], 5)


def _sound(path, settings):
    if settings["focus"]["sound"] and os.path.exists(path):
        for player in ("pw-play", "paplay"):
            if shutil.which(player):
                subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return


def _dnd(on):
    """Turns Do not disturb on / off; returns what it was before."""
    r = _quiet(["swaync-client", "-D"], 3)
    before = bool(r and r.stdout.strip() == "true")
    _quiet(["swaync-client", "--dnd-on" if on else "--dnd-off", "--skip-wait"], 3)
    return before


def _sites(on, settings):
    if not os.path.exists(HOSTS_TOOL):
        return False
    if on:
        sites = split_list(settings["focus"]["block_sites"])
        if not sites:
            return False
        r = _quiet(["pkexec", HOSTS_TOOL, "on", *sites], 20)
    else:
        r = _quiet(["pkexec", HOSTS_TOOL, "off"], 20)
    return bool(r and r.returncode == 0)


def _close_blocked(settings):
    blocked = split_list(settings["focus"]["block_apps"])
    if not blocked:
        return
    r = _quiet(["hyprctl", "clients", "-j"], 3)
    try:
        clients = json.loads(r.stdout) if r else []
    except ValueError:
        return
    for pid, name in to_close(clients, blocked):
        if isinstance(pid, int) and pid > 1:
            try:
                os.kill(pid, 15)
            except OSError:
                continue
            _island("action-unavailable-symbolic", f"{name} waits until focus ends")


def _begin_focus(state, settings):
    state["sites"] = _sites(True, settings) if settings["focus"]["block_sites"] else False
    if settings["focus"]["quiet"]:
        state["dnd_before"] = _dnd(True)


def _end_focus(state, settings):
    """Undo the blocking (keeps the state file's phase as is)."""
    if state.get("sites"):
        _sites(False, settings)
        state["sites"] = False
    if settings["focus"]["quiet"] and "dnd_before" in state:
        _dnd(state.pop("dnd_before"))


def _record(start, end):
    _write(LOG, log_session(_read(LOG, []), start, end))


def _spawn_runner():
    tool = os.path.expanduser("~/.local/bin/lennox-focus")
    try:
        subprocess.Popen(["setsid", "-f", tool, "run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL)
    except OSError:
        pass


def start(minutes=None, now=None):
    now = time.time() if now is None else now
    settings = S.load()
    current = load_state()
    if current and current["phase"] == "focus":
        return current
    if current:                                   # a break: end it first
        save_state(None)
    minutes = int(minutes or settings["focus"]["minutes"])
    state = {"phase": "focus", "start": now, "end": now + minutes * 60, "minutes": minutes,
             "round": 1, "rounds": max(1, int(settings["focus"]["rounds"])), "length": minutes}
    _begin_focus(state, settings)
    save_state(state)
    _island("find-location-symbolic", f"Focus · {minutes} min")
    _spawn_runner()
    return state


def stop(now=None, quiet=False):
    now = time.time() if now is None else now
    state = load_state()
    if not state:
        return None
    settings = S.load()
    if state["phase"] == "focus":
        _record(state["start"], min(now, state["end"]))
        _end_focus(state, settings)
        if not quiet:
            done = int((min(now, state["end"]) - state["start"]) // 60)
            _island("find-location-symbolic", f"Focus stopped · {done} min done")
    save_state(None)
    return state


def more(minutes=5):
    state = load_state()
    if state:
        state["end"] += minutes * 60
        state["minutes"] = state.get("minutes", 0) + (minutes if state["phase"] == "focus" else 0)
        save_state(state)
    return state


def step(now, settings):
    """One check of the watcher. Returns False when there's nothing left to watch."""
    state = load_state()
    if not state:
        return False
    if state["phase"] == "focus":
        if now < state["end"]:
            _close_blocked(settings)
            return True
        _record(state["start"], state["end"])
        _end_focus(state, settings)
        _sound(SOUND_END, settings)
        rnd, rounds = state.get("round", 1), state.get("rounds", 1)
        last = rnd >= rounds
        # Between rounds a short break; after the last round of a set, a long one
        pause = settings["focus"]["long_break_minutes"] if last and rounds > 1 else settings["focus"]["break_minutes"]
        if pause <= 0 and not last:
            _next_round(state, now, settings)
            return True
        if pause <= 0:
            _notify("Focus done", f"{state['minutes']} minutes. Nice work.")
            save_state(None)
            return False
        what = "Set complete: take a long break" if last and rounds > 1 else "Focus done: take a break"
        _notify(what, f"{state['minutes']} minutes done. Stand up, drink some water, back in {pause} min."
                      + (f" Next: round {rnd + 1} of {rounds}." if not last else ""), "emblem-ok-symbolic")
        state.update({"phase": "break", "start": now, "end": now + pause * 60})
        save_state(state)
        return True
    if now >= state["end"]:
        if state.get("round", 1) < state.get("rounds", 1):
            _sound(SOUND_BREAK_OVER, settings)
            _next_round(state, now, settings)
            return True
        _sound(SOUND_BREAK_OVER, settings)
        _notify("Break's over", "Start another focus session from the island, the quick panel or SUPER + F12.",
                "find-location-symbolic")
        save_state(None)
        return False
    return True


def _next_round(state, now, settings):
    """The break is over (or skipped) and there are rounds left: focus again."""
    minutes = state.get("length") or settings["focus"]["minutes"]
    state.update({"phase": "focus", "start": now, "end": now + minutes * 60, "minutes": minutes,
                  "round": state.get("round", 1) + 1})
    _begin_focus(state, settings)
    save_state(state)
    _island("find-location-symbolic", f"Focus · round {state['round']} of {state['rounds']}")
    _notify(f"Round {state['round']} of {state['rounds']}", f"{minutes} minutes. Go.", "find-location-symbolic")


def skip(now=None):
    """Skip the break: the next round starts now (or, after the last round, it's all over)."""
    now = time.time() if now is None else now
    state = load_state()
    if not state or state["phase"] != "break":
        return state
    if state.get("round", 1) < state.get("rounds", 1):
        _next_round(state, now, S.load())
        return load_state()
    save_state(None)
    return None


def run():
    """The watcher: one per login, until the session and its break end."""
    os.makedirs(os.path.dirname(RUN_LOCK), exist_ok=True)
    lock = open(RUN_LOCK, "w")  # noqa: SIM115  held for the life of the process
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                   # already watching
    while True:
        try:
            if not step(time.time(), S.load()):
                return 0
        except Exception as e:  # noqa: BLE001  keep watching; a hiccup must not leave sites blocked
            print(f"lennox-focus: {e!r}", file=sys.stderr)
        time.sleep(2)


def restore():
    """At login: a session that was running before a restart picks up again (or is closed off)."""
    state = load_state()
    if not state:
        return
    if state["phase"] == "focus" and time.time() < state["end"]:
        _spawn_runner()
        return
    settings = S.load()
    if state["phase"] == "focus":
        _record(state["start"], state["end"])
    if state.get("sites"):
        _sites(False, settings)
    save_state(None)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    words = [a for a in argv[2:] if not a.startswith("--")]
    arg = words[0] if words else None
    if arg is not None and not arg.isdigit():
        print("Minutes must be a number", file=sys.stderr)
        return 2
    if mode == "start":
        start(int(arg) if arg else None)
    elif mode == "stop":
        stop(quiet="--quiet" in argv)
    elif mode == "toggle":
        state = load_state()
        if state and state["phase"] == "focus":
            stop()
        else:
            start()
    elif mode == "skip":
        skip()
    elif mode == "more":
        more(int(arg) if arg else 5)
    elif mode == "status":
        print(json.dumps(status(load_state(), time.time())))
    elif mode == "stats":
        print(json.dumps(stats(_read(LOG, []), time.time())))
    elif mode == "run":
        return run()
    elif mode == "restore":
        restore()
    else:
        print("usage: lennox-focus start [MIN] | stop | toggle | more [MIN] | status | stats", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
