"""Profiles by place or time: one rule per Wi-Fi network or time of day.

    python3 -m lennox.autoprofile watch           (started at login) follows the Wi-Fi and the clock
    python3 -m lennox.autoprofile check|list
    python3 -m lennox.autoprofile add "wifi:School -> quiet dnd volume=20"
    python3 -m lennox.autoprofile add "time:22:00-06:00 -> quiet dnd night=on"
    python3 -m lennox.autoprofile remove N

A rule fits while you are on that Wi-Fi network, or while the clock is inside
the time range. The first rule that fits wins; when none fits, everything it
changed goes back. Words after the arrow: quiet|balanced|max (power mode),
dnd (hold notifications), volume=N, night=on|off.
"""

import fcntl
import json
import os
import sys
import time

from . import settings as S
from . import sh

RULES = os.path.join(S.CONFIG_DIR, "auto-profiles.json")
STATE = os.path.join(S.RUNTIME_DIR, "autoprofile.json")
LOCK = os.path.join(S.RUNTIME_DIR, "autoprofile-watch.lock")
EVERY = 20
PERF = ("quiet", "balanced", "max")


def parse_rule(text):
    """'wifi:School -> quiet dnd volume=20' -> rule dict (None if it makes no sense)."""
    left, _, right = text.partition("->")
    when, _, value = left.strip().partition(":")
    when, value = when.strip().lower(), value.strip()
    if when not in ("wifi", "time") or not value:
        return None
    if when == "time" and parse_range(value) is None:
        return None
    rule = {"when": when, "value": value}
    for word in right.split():
        key, _, arg = word.partition("=")
        if word in PERF:
            rule["perf"] = word
        elif word == "dnd":
            rule["dnd"] = True
        elif key == "volume" and arg.isdigit():
            rule["volume"] = max(0, min(100, int(arg)))
        elif key == "night" and arg in ("on", "off"):
            rule["night"] = arg
        else:
            return None
    return rule if len(rule) > 2 else None


def describe(rule):
    what = [rule.get("perf", ""), "notifications held" if rule.get("dnd") else "",
            f"volume {rule['volume']}%" if "volume" in rule else "",
            f"night light {rule['night']}" if rule.get("night") else ""]
    return f"{'Wi-Fi' if rule['when'] == 'wifi' else 'Time'} {rule['value']}: " + ", ".join(w for w in what if w)


def parse_range(text):
    """'22:00-06:00' -> (start minute, end minute) or None."""
    try:
        a, b = text.split("-")
        h1, m1 = (int(x) for x in a.split(":"))
        h2, m2 = (int(x) for x in b.split(":"))
    except ValueError:
        return None
    if not (0 <= h1 < 24 and 0 <= h2 < 24 and 0 <= m1 < 60 and 0 <= m2 < 60):
        return None
    return h1 * 60 + m1, h2 * 60 + m2


def in_range(rng, minute):
    start, end = rng
    return start <= minute < end if start <= end else minute >= start or minute < end


def match(rules, wifi, minute):
    """The first rule that fits right now (a Wi-Fi name and the minute of the day)."""
    for rule in rules:
        if rule["when"] == "wifi" and wifi and rule["value"].lower() == wifi.lower():
            return rule
        if rule["when"] == "time":
            rng = parse_range(rule["value"])
            if rng and in_range(rng, minute):
                return rule
    return None


def load_rules(path=RULES):
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f).get("rules", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [r for r in raw if isinstance(r, dict) and r.get("when") in ("wifi", "time") and r.get("value")]


def save_rules(rules, path=RULES):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"rules": rules}, f, indent=1)
    os.replace(path + ".tmp", path)


def decide(state, found):
    if found is None:
        return "undo" if state else None
    if state is None:
        return "apply"
    return None if state.get("rule") == found else "switch"


def wifi_name():
    for line in sh.out(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"], 4).splitlines():
        if line.startswith("yes:"):
            return line[4:].replace("\\:", ":")
    return ""


def _volume():
    text = sh.out(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], 3)          # "Volume: 0.45"
    try:
        return round(float(text.split()[1]) * 100)
    except (IndexError, ValueError):
        return None


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
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def apply(rule):
    prev = {}
    if rule.get("perf"):
        prev["perf"] = sh.out([sh.bin_path("lennox-perf"), "status"])
        sh.run([sh.bin_path("lennox-perf"), rule["perf"]])
    if rule.get("dnd"):
        prev["dnd"] = sh.out(["swaync-client", "-D"], 3) == "true"
        sh.run(["swaync-client", "--dnd-on", "--skip-wait"], 3)
    if "volume" in rule:
        prev["volume"] = _volume()
        sh.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{rule['volume']}%"], 3)
    if rule.get("night"):
        prev["night"] = sh.out([sh.bin_path("lennox-nightlight"), "status"])
        sh.run([sh.bin_path("lennox-nightlight"), rule["night"]])
    _write_state({"rule": rule, "prev": prev})
    sh.island("preferences-system-symbolic", describe(rule).split(":")[0] + " profile", 3)


def undo(state):
    prev = state.get("prev", {})
    if prev.get("perf") in PERF:
        sh.run([sh.bin_path("lennox-perf"), prev["perf"]])
    if prev.get("dnd") is False:
        sh.run(["swaync-client", "--dnd-off", "--skip-wait"], 3)
    if prev.get("volume") is not None:
        sh.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{prev['volume']}%"], 3)
    if prev.get("night") in ("on", "off"):
        sh.run([sh.bin_path("lennox-nightlight"), prev["night"]])
    _write_state(None)


def check(now=None):
    state = _read_state()
    gaming = sh.out([sh.bin_path("lennox-mode"), "game", "status"]) == "on"
    if not S.load()["auto"]["on"] or gaming:
        if state:
            undo(state)
        return None
    t = time.localtime(now)
    found = match(load_rules(), wifi_name(), t.tm_hour * 60 + t.tm_min)
    action = decide(state, found)
    if action in ("undo", "switch"):
        undo(state)
    if action in ("apply", "switch"):
        apply(found)
    return action


def watch():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")  # noqa: SIM115  held for the life of the process
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    while True:
        try:
            check()
        except Exception:  # noqa: BLE001  one hiccup must not stop the watcher
            pass
        time.sleep(EVERY)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "list"
    if mode == "watch":
        return watch()
    if mode == "check":
        print(check() or "nothing to do")
    elif mode == "list":
        print(json.dumps(load_rules(), ensure_ascii=False))
    elif mode == "add" and len(argv) > 2:
        rule = parse_rule(argv[2])
        if rule is None:
            print('Not a rule. Example: "wifi:School -> quiet dnd volume=20"', file=sys.stderr)
            return 1
        save_rules(load_rules() + [rule])
    elif mode == "remove" and len(argv) > 2 and argv[2].isdigit():
        rules = load_rules()
        if int(argv[2]) < len(rules):
            del rules[int(argv[2])]
            save_rules(rules)
    else:
        print("usage: lennox-autoprofile watch | check | list | add RULE | remove N", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
