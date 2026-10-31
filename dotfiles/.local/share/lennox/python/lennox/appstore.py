"""App store: Arch, AUR and Flathub in one search; install, update, remove.

    python3 -m lennox.appstore search WORDS...          results as JSON
    python3 -m lennox.appstore install|update|remove SOURCE ID
    python3 -m lennox.appstore installed                your apps, as JSON

SOURCE is arch, aur or flathub. Installing opens a small terminal, so you see
what happens and type your password there (AUR apps are built on your PC).
"""

import json
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

AUR_RPC = "https://aur.archlinux.org/rpc/v5/search/{}?by=name-desc"
SOURCES = {"arch": "Arch", "aur": "AUR", "flathub": "Flathub"}
LIMIT = 25


def _run(argv, timeout=30):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def aur_helper():
    for helper in ("yay", "paru"):
        if shutil.which(helper):
            return helper
    return None


# ---------------------------------------------------------------- the three sources

def parse_pacman(text):
    """`pacman -Ss` output -> results."""
    out, last = [], None
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            if last is not None:
                last["description"] = line.strip()
            continue
        m = re.match(r"(\S+)/(\S+) (\S+)(.*)", line)
        if not m:
            last = None
            continue
        rest = m.group(4)
        local = re.search(r"\[installed(?:: ([^\]]+))?\]", rest)
        last = {"source": "arch", "id": m.group(2), "name": m.group(2), "version": m.group(3),
                "repo": m.group(1), "description": "", "installed": bool(local),
                "update": bool(local and local.group(1))}
        out.append(last)
    return out


def search_arch(words):
    if not shutil.which("pacman"):
        return []
    code, out = _run(["pacman", "-Ss", "--", *words])
    return parse_pacman(out) if code == 0 else []


def installed_versions():
    """{name: version} of everything pacman has installed."""
    code, out = _run(["pacman", "-Q"])
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line) if code == 0 else {}


def parse_aur(data, local):
    out = []
    for r in (data or {}).get("results") or []:
        name = r.get("Name")
        if not name:
            continue
        mine = local.get(name)
        out.append({"source": "aur", "id": name, "name": name, "version": r.get("Version", ""),
                    "description": r.get("Description") or "", "votes": r.get("NumVotes", 0),
                    "popularity": r.get("Popularity", 0), "installed": mine is not None,
                    "update": mine is not None and mine != r.get("Version"),
                    "outdated": bool(r.get("OutOfDate"))})
    out.sort(key=lambda r: -float(r["popularity"] or 0))
    return out[:LIMIT]


def search_aur(words, local):
    query = max(words, key=len)                  # the AUR searches one word; take the most telling
    if len(query) < 2:
        return []
    try:
        with urllib.request.urlopen(AUR_RPC.format(urllib.parse.quote(query)), timeout=8) as reply:
            data = json.load(reply)
    except (OSError, ValueError):
        return []
    results = parse_aur(data, local)
    rest = [w.lower() for w in words if w != query]
    return [r for r in results if all(w in (r["name"] + " " + r["description"]).lower() for w in rest)]


def flatpak_installed():
    if not shutil.which("flatpak"):
        return set()
    code, out = _run(["flatpak", "list", "--app", "--columns=application"])
    return set(out.split()) if code == 0 else set()


def parse_flatpak(text, installed):
    out = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 5 or "flathub" not in parts[4]:
            continue
        name, description, app, version = parts[:4]
        out.append({"source": "flathub", "id": app, "name": name, "version": version,
                    "description": description, "installed": app in installed, "update": False})
    return out


def search_flathub(words):
    if not shutil.which("flatpak"):
        return []
    code, out = _run(["flatpak", "search", "--columns=name,description,application,version,remotes",
                      " ".join(words)])
    return parse_flatpak(out, flatpak_installed()) if code == 0 else []


# ---------------------------------------------------------------- one list

def rank(results, words):
    """Exact names first, then names that contain the words, then the rest.
    Within that: Flathub (sandboxed apps), Arch, then AUR, as listed by each."""
    query = " ".join(words).lower()
    order = {"flathub": 0, "arch": 1, "aur": 2}

    def key(item):
        index, r = item
        names = {r["name"].lower(), r["id"].lower(), r["id"].lower().rsplit(".", 1)[-1]}
        if query in names:
            match = 0
        elif any(query in n for n in names):
            match = 1
        else:
            match = 2
        return (match, order[r["source"]], index)

    return [r for _, r in sorted(enumerate(results), key=key)]


def search(words):
    words = [w for w in words if w.strip()]
    if not words:
        return []
    local = installed_versions()
    found = search_flathub(words)[:LIMIT] + search_arch(words)[:LIMIT * 2] + search_aur(words, local)
    return rank(found, words)[:60]


def installed():
    apps = []
    if shutil.which("flatpak"):
        code, out = _run(["flatpak", "list", "--app", "--columns=name,application,version"])
        for line in out.splitlines() if code == 0 else []:
            parts = line.split("\t")
            if len(parts) >= 2:
                apps.append({"source": "flathub", "id": parts[1], "name": parts[0],
                             "version": parts[2] if len(parts) > 2 else "", "installed": True})
    code, out = _run(["pacman", "-Qem"])           # AUR (foreign) packages you installed
    for line in out.splitlines() if code == 0 else []:
        name, _, version = line.partition(" ")
        apps.append({"source": "aur", "id": name, "name": name, "version": version, "installed": True})
    return apps


# ---------------------------------------------------------------- doing it

def command(action, source, ident):
    """The shell command for an action, or None if it can't be done here."""
    if not re.fullmatch(r"[A-Za-z0-9@._+-]+", ident or ""):
        return None
    q = shlex.quote(ident)
    helper = aur_helper()
    if source == "arch":
        return {"install": f"sudo pacman -S --needed {q}", "update": f"sudo pacman -S {q}",
                "remove": f"sudo pacman -Rns {q}"}.get(action)
    if source == "aur":
        if not helper:
            return None
        return {"install": f"{helper} -S --needed {q}", "update": f"{helper} -S {q}",
                "remove": f"{helper} -Rns {q}"}.get(action)
    if source == "flathub":
        return {"install": f"flatpak install -y flathub {q}", "update": f"flatpak update -y {q}",
                "remove": f"flatpak uninstall -y {q}"}.get(action)
    return None


VERBS = {"install": "Installing", "update": "Updating", "remove": "Removing"}


def terminal_script(action, source, ident):
    cmd = command(action, source, ident)
    if cmd is None:
        return None
    note = ""
    if source == "aur" and action != "remove":
        note = ("echo 'AUR apps are made by the community and built on your PC.'; "
                "echo 'When yay asks to review the build files, Enter skips that.'; echo; ")
    return (f"printf '\\e[1m{VERBS[action]} {ident} ({SOURCES[source]})\\e[0m\\n\\n'; {note}"
            f"if {cmd}; then echo; echo 'Done.'; sleep 2; "
            f"else echo; echo 'It did not work (see above).'; read -rp 'Press Enter to close'; exit 1; fi")


def run_action(action, source, ident):
    """Runs in a terminal and waits for it to close; exit code 0 means it worked."""
    script = terminal_script(action, source, ident)
    if script is None:
        print(f"Can't {action} {ident} from {source}", file=sys.stderr)
        return 2
    term = shutil.which("kitty")
    if term:
        title = f"{VERBS[action]} {ident}"
        subprocess.call([term, "--class", "lennox-floating", "--title", title, "bash", "-c", script])
    else:
        subprocess.call(["bash", "-c", script])
    # The terminal's exit code isn't the command's: look at what's installed now
    there = is_installed(source, ident)
    return 0 if there == (action != "remove") else 1


def is_installed(source, ident):
    if source == "flathub":
        return ident in flatpak_installed()
    return _run(["pacman", "-Q", ident])[0] == 0


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "search":
        print(json.dumps(search(argv[2:]), ensure_ascii=False))
        return 0
    if mode == "installed":
        print(json.dumps(installed(), ensure_ascii=False))
        return 0
    if mode in VERBS and len(argv) == 4 and argv[2] in SOURCES:
        return run_action(mode, argv[2], argv[3])
    print("usage: lennox-apps search WORDS | installed | install|update|remove arch|aur|flathub ID",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
