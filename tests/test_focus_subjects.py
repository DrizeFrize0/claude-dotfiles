"""Focus sessions with a subject: logged, summed per week, started from the CLI."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python")
sys.path.insert(0, ROOT)
from lennox import focus  # noqa: E402

NOW = time.mktime((2026, 11, 4, 12, 0, 0, 0, 0, -1))
DAY = 86400


class Log(unittest.TestCase):
    def test_subject_is_logged_only_when_given(self):
        log = focus.log_session([], NOW - 3000, NOW, "Math")
        self.assertEqual(log[0]["subject"], "Math")
        self.assertNotIn("subject", focus.log_session([], NOW - 3000, NOW)[0])

    def test_week_by_subject(self):
        log = []
        log = focus.log_session(log, NOW - 3000, NOW, "Math")                       # 50
        log = focus.log_session(log, NOW - DAY - 1800, NOW - DAY, "Physics")        # 30
        log = focus.log_session(log, NOW - DAY - 3000, NOW - DAY - 1200, "Math")    # 30
        log = focus.log_session(log, NOW - 9 * DAY - 3000, NOW - 9 * DAY, "Math")  # too old for the week
        log = focus.log_session(log, NOW - 2 * DAY - 600, NOW - 2 * DAY)            # no subject
        st = focus.stats(log, NOW)
        self.assertEqual(st["subjects"], {"Math": 80, "Physics": 30})
        self.assertEqual(list(st["subjects"]), ["Math", "Physics"])                 # biggest first

    def test_cli_start_stop(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home + "/.config", XDG_STATE_HOME=home + "/.local/state",
                       XDG_RUNTIME_DIR=home + "/run", PYTHONPATH=ROOT, LENNOX_FOCUS_HOSTS_TOOL="/bin/true", PATH="/usr/bin:/bin")
            os.makedirs(home + "/run")

            def cli(*a):
                return subprocess.run([sys.executable, "-m", "lennox.focus", *a], env=env, capture_output=True, text=True)
            self.assertEqual(cli("start", "25", "--subject=Chemistry").returncode, 0)
            state = json.load(open(home + "/.local/state/lennox/focus.json"))
            self.assertEqual((state["subject"], state["minutes"]), ("Chemistry", 25))
            self.assertEqual(cli("stop", "--quiet").returncode, 0)
            self.assertEqual(cli("status").stdout.strip(), '{"active": false}')


if __name__ == "__main__":
    unittest.main()
