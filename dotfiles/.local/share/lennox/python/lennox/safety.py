"""Safety: restore points for the system and copies of your files.

    python3 -m lennox.safety status [--json]    what is protected, and when it was last backed up
    python3 -m lennox.safety snap [TEXT]        a system restore point right now
    python3 -m lennox.safety list               the restore points
    python3 -m lennox.safety undo [--yes]       take back the last update (what the update changed on the system)
    python3 -m lennox.safety drives             the drives your files can be copied to
    python3 -m lennox.safety files [FOLDER]     copy your folders to a drive (nothing is ever deleted there)
    python3 -m lennox.safety restore [FOLDER]   copy them back from the drive

System restore points need btrfs and snapper (the installer sets both up; every update takes one by
itself). The safest way back is still the boot menu: "Arch Linux snapshots" boots a working desktop
from the restore point you pick. `undo` is the quick way for a bad update you notice straight away.

File copies skip caches and never delete anything on the drive. Drives formatted for Windows (exFAT, NTFS,
FAT) cannot keep Linux permissions, so those are copied by name and date and the private SSH keys get
their permissions back when you restore.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

from . import settings as S
from . import sh

STATE = os.path.join(S.STATE_DIR, "safety.json")
DEFAULT_FOLDERS = "Documents, Pictures, Desktop, Videos, Music, .ssh, .gnupg, .minecraft, .zen"
SUDO = os.environ.get("LENNOX_SAFETY_SUDO", "sudo").split()      # tests run without it
HOME = os.path.expanduser("~")
WINDOWS_FS = ("exfat", "vfat", "ntfs", "ntfs3", "fuseblk", "msdos")
MOUNT_ROOTS = ("/run/media/", "/media/", "/mnt/")
EXCLUDES = ["Cache", "cache", "Cache2", "cache2", "GPUCache", "Code Cache", "ShaderCache", "node_modules", ".tmp",
            "Trash", "*.tmp", "*.lock", "lock", ".parentlock", "crashes", "minidumps"]
KEY_FILES = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")


# ------------------------------------------------------------------ state

def load_state(path=None):
    try:
        with open(path or STATE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(data, path=None):
    path = path or STATE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def days_since(stamp, now=None):
    """Whole days since a timestamp (None if it never happened)."""
    if not stamp:
        return None
    return max(0, int(((now or time.time()) - stamp) // 86400))


# ------------------------------------------------------------------ system restore points (snapper)

def snapper_ready():
    return shutil.which("snapper") is not None


def snapper(args, timeout=60):
    return sh.run(SUDO + ["snapper", "-c", "root"] + args, timeout)


def list_snapshots():
    """[{number, type, pre, date, description}] newest last; [] when snapper is not set up."""
    if not snapper_ready():
        return []
    code, out, _err = snapper(["--jsonout", "list", "--columns", "number,type,pre-number,date,description"])
    if code != 0:
        return []
    try:
        rows = json.loads(out).get("root", [])
    except (ValueError, AttributeError):
        return []
    snaps = []
    for r in rows:
        try:
            number = int(r.get("number", 0))
        except (TypeError, ValueError):
            continue
        if number == 0:                       # snapshot 0 is "now", not a restore point
            continue
        pre = r.get("pre-number")
        snaps.append({"number": number, "type": r.get("type", ""), "pre": int(pre) if str(pre).isdigit() else None,
                      "date": str(r.get("date", "")), "description": str(r.get("description", ""))})
    return sorted(snaps, key=lambda s: s["number"])


def last_update_pair(snaps):
    """(pre, post) of the newest pre/post pair an update took, or None."""
    for s in reversed(snaps):
        if s["type"] == "post" and s["pre"]:
            for p in snaps:
                if p["number"] == s["pre"]:
                    return p, s
    return None


def snap(text="Lennox restore point"):
    """Take a restore point. Returns its number, or None."""
    if not snapper_ready():
        return None
    code, out, err = snapper(["create", "--type", "single", "--cleanup-algorithm", "number", "--print-number",
                              "--description", text])
    if code != 0:
        return None
    number = out.strip().splitlines()[-1] if out.strip() else ""
    return int(number) if number.isdigit() else None


def undo_last_update(yes=False, ask=input):
    """Reverts what the last update changed on the system. Returns (done, message)."""
    pair = last_update_pair(list_snapshots())
    if not pair:
        return False, "No update restore point found (the next update takes one by itself)."
    pre, post = pair
    if not yes:
        print(f"This takes back what the update on {post['date']} changed ({pre['description'] or 'update'}).")
        print("Your files in your home folder are not touched. Restart afterwards.")
        if ask("Type UNDO to continue: ").strip() != "UNDO":
            return False, "Nothing was changed."
    safety = snap(f"Before undoing update {pre['number']}..{post['number']}")
    code, _out, err = snapper(["undochange", f"{pre['number']}..{post['number']}"], timeout=600)
    if code != 0:
        return False, f"Could not undo it ({err.strip() or 'snapper failed'}). Restore from the boot menu instead."
    return True, ("Done" + (f" (a restore point of how it was before is number {safety})" if safety else "")
                  + ". Restart the laptop now.")


# ------------------------------------------------------------------ files to a drive

def mounts(path="/proc/self/mounts"):
    found = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    found.append((parts[1].replace("\\040", " "), parts[2]))
    except OSError:
        pass
    return found


def drives(mount_list=None):
    """[(path, fstype, free_bytes)] mounted drives that are not the system: USB sticks, the Windows drive..."""
    out = []
    for where, kind in (mount_list if mount_list is not None else mounts()):
        if not where.startswith(MOUNT_ROOTS) or kind in ("tmpfs", "overlay", "squashfs", "autofs"):
            continue
        if not os.access(where, os.W_OK):
            continue
        try:
            st = os.statvfs(where)
            out.append((where, kind, st.f_bavail * st.f_frsize))
        except OSError:
            continue
    return sorted(out, key=lambda d: -d[2])


def fs_of(path, mount_list=None):
    """The filesystem type of the mount that holds path (longest matching mount)."""
    best, kind = "", ""
    for where, k in (mount_list if mount_list is not None else mounts()):
        if (path == where or path.startswith(where.rstrip("/") + "/")) and len(where) > len(best):
            best, kind = where, k
    return kind


def folders(settings=None):
    text = S.get(settings or S.load(), "safety.folders") or DEFAULT_FOLDERS
    names = [n.strip().strip("/") for n in str(text).split(",")]
    return [n for n in names if n and ".." not in n.split("/")]


def target(dest=None, settings=None, mount_list=None):
    """The folder file copies go to: DEST, the folder from Settings, or the roomiest drive."""
    settings = settings or S.load()
    base = dest or S.get(settings, "safety.drive") or ""
    if not base:
        found = drives(mount_list)
        if not found:
            return None
        base = found[0][0]
    return os.path.join(os.path.expanduser(base), "lennox-files", socket.gethostname() or "laptop")


def rsync_args(kind, source, dest, dry=False):
    flags = ["-rt", "--modify-window=2", "--no-perms", "--no-owner", "--no-group"] if kind in WINDOWS_FS else ["-a"]
    argv = ["rsync"] + flags + ["--info=stats1,progress2", "--human-readable"]
    for pattern in EXCLUDES:
        argv += ["--exclude", pattern]
    if dry:
        argv.append("--dry-run")
    return argv + [source.rstrip("/") + "/", dest.rstrip("/") + "/"]


def fix_permissions(home=HOME):
    """exFAT and NTFS forget Linux permissions: private keys must be private again."""
    ssh = os.path.join(home, ".ssh")
    gpg = os.path.join(home, ".gnupg")
    for folder in (ssh, gpg):
        if os.path.isdir(folder):
            os.chmod(folder, 0o700)
    if os.path.isdir(ssh):
        for name in os.listdir(ssh):
            path = os.path.join(ssh, name)
            if os.path.isfile(path) and (name in KEY_FILES or name.startswith("id_") and not name.endswith(".pub")):
                os.chmod(path, 0o600)


def copy_files(dest=None, only=None, dry=False, mount_list=None, home=HOME, say=print):
    """Copies the folders to the drive. Returns (ok, message)."""
    if not shutil.which("rsync"):
        return False, "rsync is missing: sudo pacman -S rsync"
    where = target(dest, mount_list=mount_list)
    if not where:
        return False, "No drive found. Plug in a USB stick or open the Windows drive in Files, then try again."
    kind = fs_of(where, mount_list)
    wanted = [only.strip("/")] if only else folders()
    total, missing = 0, []
    for name in wanted:
        source = os.path.join(home, name)
        if not os.path.exists(source):
            missing.append(name)
            continue
        say(f":: {name}")
        out = os.path.join(where, name)
        if os.path.isfile(source):
            os.makedirs(where, exist_ok=True)
            code = subprocess.run(["rsync", "-t", source, os.path.join(where, os.path.basename(source))],
                                  check=False).returncode
        else:
            os.makedirs(out, exist_ok=True)
            code = subprocess.run(rsync_args(kind, source, out, dry), check=False).returncode
        if code not in (0, 23, 24):           # 23/24: some files vanished or could not be read (open browser files)
            return False, f"rsync stopped on {name} (code {code}). The drive may be full or unplugged."
        total += 1
    if not dry and total:
        state = load_state()
        state["files"] = {"time": int(time.time()), "dest": where, "folders": total}
        save_state(state)
    note = f" ({len(missing)} not found: {', '.join(missing)})" if missing else ""
    return True, (f"{total} folder(s) {'would be copied' if dry else 'copied'} to {where}{note}")


def restore_files(source=None, only=None, mount_list=None, home=HOME, say=print):
    """Copies the folders back from the drive. Returns (ok, message)."""
    if not shutil.which("rsync"):
        return False, "rsync is missing: sudo pacman -S rsync"
    where = target(source, mount_list=mount_list)
    if not where or not os.path.isdir(where):
        return False, f"No copy found{(' in ' + where) if where else ''}. Plug the drive in first."
    kind = fs_of(where, mount_list)
    names = [only.strip("/")] if only else folders()
    count = 0
    for name in names:
        src = os.path.join(where, name)
        if not os.path.isdir(src):
            continue
        say(f":: {name}")
        os.makedirs(os.path.join(home, name), exist_ok=True)
        flags = ["-rt"] if kind in WINDOWS_FS else ["-a"]
        code = subprocess.run(["rsync"] + flags + ["--info=stats1,progress2", "--human-readable",
                                                   src.rstrip("/") + "/", os.path.join(home, name) + "/"],
                              check=False).returncode
        if code not in (0, 23, 24):
            return False, f"rsync stopped on {name} (code {code})."
        count += 1
    fix_permissions(home)
    return (count > 0), (f"{count} folder(s) restored from {where}. Close and reopen Zen to use the restored profile."
                         if count else f"Nothing to restore in {where}.")


# ------------------------------------------------------------------ status

def status(now=None, snaps=None):
    snaps = list_snapshots() if snaps is None else snaps
    pair = last_update_pair(snaps)
    files = load_state().get("files") or {}
    since = days_since(files.get("time"), now)
    settings = S.load()
    return {
        "snapper": snapper_ready(),
        "snapshots": len(snaps),
        "last_snapshot": snaps[-1]["date"] if snaps else "",
        "last_update_pair": [pair[0]["number"], pair[1]["number"]] if pair else None,
        "files_days": since,
        "files_dest": files.get("dest", ""),
        "remind_days": S.get(settings, "safety.remind_days") or 14,
        "drives": [d[0] for d in drives()],
    }


def advice(info):
    """[(level, text, hint)] for the doctor and the Settings page."""
    out = []
    if not info["snapper"]:
        out.append(("warn", "No system restore points", "On btrfs the installer sets them up (snapper + snap-pac)."))
    elif info["snapshots"] == 0:
        out.append(("warn", "No restore point taken yet", "lennox-safety snap"))
    else:
        out.append(("ok", f"{info['snapshots']} system restore point(s); the boot menu can start from any of them", ""))
    days = info["files_days"]
    if days is None:
        out.append(("warn", "Your files have never been copied to a drive", "Plug in a drive and run: lennox-safety files"))
    elif days > info["remind_days"]:
        out.append(("warn", f"Your files were last copied {days} days ago", "Plug in the drive and run: lennox-safety files"))
    else:
        out.append(("ok", f"Files copied to a drive {days} day(s) ago", ""))
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    rest = [a for a in argv[2:] if not a.startswith("--")]
    flags = {a for a in argv[2:] if a.startswith("--")}
    if cmd == "status":
        info = status()
        if "--json" in flags:
            info["advice"] = [{"level": l, "text": t, "hint": h} for l, t, h in advice(info)]
            print(json.dumps(info))
            return 0
        for level, text, hint in advice(info):
            print(("  ok  " if level == "ok" else "  !   ") + text + (f"\n        {hint}" if hint else ""))
        return 0
    if cmd == "snap":
        number = snap(" ".join(rest) or "Restore point by hand")
        print(f"Restore point {number} taken." if number else "Could not take a restore point (btrfs + snapper needed).")
        return 0 if number else 1
    if cmd == "list":
        snaps = list_snapshots()
        for s in snaps[-30:]:
            print(f"{s['number']:>4}  {s['type']:<6} {s['date']:<22} {s['description']}")
        if not snaps:
            print("No restore points (btrfs + snapper needed).")
        return 0
    if cmd == "undo":
        done, message = undo_last_update(yes="--yes" in flags)
        print(message)
        return 0 if done else 1
    if cmd == "drives":
        found = drives()
        for path, kind, free in found:
            print(f"{path}  ({kind}, {free // 2**30} GB free)")
        if not found:
            print("No drive found.")
        return 0 if found else 1
    if cmd in ("files", "restore"):
        fn = copy_files if cmd == "files" else restore_files
        kwargs = {"dry": "--dry-run" in flags} if cmd == "files" else {}
        dest = None
        only = rest[0] if rest else None
        ok, message = fn(dest=dest, only=only, **kwargs) if cmd == "files" else fn(source=dest, only=only)
        print(message)
        return 0 if ok else 1
    print("usage: lennox-safety status | snap [TEXT] | list | undo | drives | files [FOLDER] | restore [FOLDER]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
