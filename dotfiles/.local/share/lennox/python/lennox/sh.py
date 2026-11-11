"""Small helpers every Lennox tool shares: run a program, read a file, notify, island."""

import os
import subprocess


def run(argv, timeout=10, data=None):
    """(exit code, stdout, stderr); (1, "", reason) if it can't start or takes too long."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False, input=data)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def out(argv, timeout=5):
    """What a program prints, trimmed, whatever its exit code ("" if it can't run)."""
    return run(argv, timeout)[1].strip()


def bin_path(name):
    return os.path.join(os.path.expanduser("~"), ".local", "bin", name)


def read_text(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def notify(title, body, icon="dialog-information"):
    run(["notify-send", "-a", "Lennox", "-i", icon, title, body], 5)


def island(icon, text, seconds=4):
    run([bin_path("lennox-widgets"), "island", "event", icon, text, str(seconds)], 3)
