"""Morning summary, study recap, tidy downloads, battery doctor, dynamic wallpaper, colors from music."""
import datetime
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import batterydoc, dynwall, morning, musiccolors, study, tidy  # noqa: E402

NOW = datetime.datetime(2026, 11, 7, 7, 30)


class Morning(unittest.TestCase):
    def test_sleep_line(self):
        self.assertIn("about 6.3 hours", morning.sleep_line({"2026-11-06": "01:10"}, NOW))     # stopped 01:10, now 07:30
        self.assertIn("a bit short", morning.sleep_line({"2026-11-06": "01:10"}, NOW))
        self.assertIn("a good night", morning.sleep_line({"2026-11-06": "23:00"}, NOW))        # 8.5 hours
        self.assertIn("go easy", morning.sleep_line({"2026-11-06": "03:30"}, NOW))             # 4 hours
        self.assertEqual(morning.sleep_line({}, NOW), "")                                        # no note: no line
        self.assertEqual(morning.sleep_line({"2026-11-06": "07:20"}, NOW), "")                  # nonsense duration: no line


class Study(unittest.TestCase):
    def log(self):
        n = time.mktime((2026, 11, 7, 15, 0, 0, 0, 0, -1))
        return [{"start": int(n - 7200), "minutes": 50, "subject": "Math"}, {"start": int(n - 3000), "minutes": 50, "subject": "Physics"},
                {"start": int(n - 86400), "minutes": 60, "subject": "Math"}], n

    def test_recap(self):
        log, n = self.log()
        lines = study.recap_lines(log, n, "Physics", 50)
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Physics: 50 min done")
        self.assertIn("Today: 1 h 40 min in 2 sessions", lines[1])
        self.assertIn("Streak: 2 days", lines[2])
        self.assertIn("Math", lines[2])

    def test_four_sessions_say_rest(self):
        n = time.mktime((2026, 11, 7, 20, 0, 0, 0, 0, -1))
        log = [{"start": int(n - 600 * k), "minutes": 20} for k in range(1, 5)]
        self.assertIn("rest your eyes", study.recap_lines(log, n, "", 20)[2])

    def test_notes_file_groups_by_day(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/Study/notes.md"
            t1 = time.mktime((2026, 11, 7, 14, 10, 0, 0, 0, -1))
            study.append_note("Math", 50, t1, path)
            study.append_note("Physics", 25, t1 + 3600, path)
            study.append_note("Math", 50, t1 + 86400, path)
            text = open(path, encoding="utf-8").read()
        self.assertEqual(text.count("## "), 2)                                          # one heading per day
        self.assertIn("- 14:10  Math  50 min", text)
        self.assertIn("- 15:10  Physics  25 min", text)
        self.assertTrue(text.startswith("# Study notes"))


class Tidy(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.now = 10_000.0
        for name, age in (("photo.PNG", 500), ("essay.pdf", 500), ("setup.AppImage", 500), ("mod.jar", 500), ("sodium.part", 500),
                          ("fresh.zip", 5), ("notes", 500), ("backup.tar.gz", 500), (".hidden.png", 500)):
            p = os.path.join(self.d, name)
            open(p, "w", encoding="utf-8").close()
            os.utime(p, (self.now - age, self.now - age))
        os.makedirs(os.path.join(self.d, "Projects"))

    def test_plan(self):
        moves = {os.path.basename(a): os.path.relpath(b, self.d) for a, b in tidy.plan(self.d, self.now, 60)}
        self.assertEqual(moves["photo.PNG"], "Images/photo.PNG")
        self.assertEqual(moves["essay.pdf"], "Documents/essay.pdf")
        self.assertEqual(moves["setup.AppImage"], "Installers/setup.AppImage")
        self.assertEqual(moves["mod.jar"], "Minecraft/mod.jar")
        self.assertEqual(moves["backup.tar.gz"], "Archives/backup.tar.gz")
        for left in ("sodium.part", "fresh.zip", "notes", ".hidden.png", "Projects"):      # unfinished, too new, unknown, hidden, folders
            self.assertNotIn(left, moves)

    def test_run_and_undo(self):
        log = self.d + "/log.json"
        done = tidy.run(self.d, self.now, 60, log_path=log)
        self.assertEqual(len(done), 5)
        self.assertTrue(os.path.exists(self.d + "/Images/photo.PNG") and not os.path.exists(self.d + "/photo.PNG"))
        self.assertEqual(tidy.run(self.d, self.now, 60, log_path=log), [])                 # nothing left to do
        back = tidy.undo(log)
        self.assertEqual(len(back), 5)
        self.assertTrue(os.path.exists(self.d + "/photo.PNG") and not os.path.exists(self.d + "/Images/photo.PNG"))
        self.assertEqual(tidy.undo(log), [])

    def test_dry_run_moves_nothing_and_names_never_collide(self):
        self.assertEqual(len(tidy.run(self.d, self.now, 60, dry=True)), 5)
        self.assertTrue(os.path.exists(self.d + "/photo.PNG"))
        os.makedirs(self.d + "/Images")
        open(self.d + "/Images/photo.PNG", "w", encoding="utf-8").close()
        tidy.run(self.d, self.now, 60, log_path=self.d + "/l.json")
        self.assertTrue(os.path.exists(self.d + "/Images/photo (1).PNG"))                   # the existing file is kept


class Battery(unittest.TestCase):
    def test_who_uses_the_battery(self):
        idle = [{"t": i, "w": 6.0, "apps": {"spotify": 2.0}, "pct": 80} for i in range(20)]
        busy = [{"t": 100 + i, "w": 16.0, "apps": {"Discord": 60.0, "spotify": 5.0}, "pct": 70} for i in range(10)]
        r = batterydoc.analyze(idle + busy, full_wh=50.0)
        self.assertAlmostEqual(r["baseline_w"], 6.0, places=1)
        self.assertEqual(r["apps"][0][0], "Discord")
        self.assertGreater(r["apps"][0][1], 0.85)
        self.assertAlmostEqual(r["avg_w"], 9.33, places=1)
        self.assertAlmostEqual(r["hours_left"], 50.0 / 9.333, places=1)
        self.assertTrue(any("Discord" in t for t in batterydoc.tips(r)))

    def test_names(self):
        rows = [(30.0, "vesktop", "/app/vesktop --type=renderer"), (25.0, "vesktop", "vesktop --gpu-process"), (3.0, "spotify", "spotify"),
                (0.2, "kworker", "kworker")]
        self.assertEqual(batterydoc.busy_apps(rows), {"Vesktop (Discord)": 55.0, "Spotify": 3.0})        # helpers add up; the idle one is left out

    def test_no_data_and_tips(self):
        self.assertIsNone(batterydoc.analyze([], 50.0))
        self.assertIn("Not enough", batterydoc.tips(None)[0])
        hot = batterydoc.analyze([{"t": 1, "w": 22.0, "apps": {"x": 1.0}, "pct": 50}] * 5, full_wh=45.0)
        self.assertTrue(any("under 3 hours" in t for t in batterydoc.tips(hot)))
        self.assertTrue(any("idle" in t.lower() for t in batterydoc.tips(hot)))


class Wallpaper(unittest.TestCase):
    ALL = {"night-owl", "aurora", "mesh-lavender", "graphite", "clouds", "dunes", "mesh-mint", "ocean-layers", "forest-mist",
           "sunset-beach", "mountains-dusk", "mesh-peach"}

    def test_slots(self):
        self.assertEqual([dynwall.slot_of(h) for h in (4, 5, 8, 16, 17, 19, 20, 23)], ["night", "dawn", "day", "day", "evening", "evening", "night", "night"])

    def test_choice_fits_the_time_and_the_weather(self):
        self.assertIn(dynwall.choose(22, "Clear", 10, self.ALL), dynwall.SLOTS["night"])
        self.assertIn(dynwall.choose(12, "Clear sky", 10, self.ALL), dynwall.SLOTS["day"])
        self.assertIn(dynwall.choose(18, "Clear", 10, self.ALL), dynwall.SLOTS["evening"])
        self.assertIn(dynwall.choose(12, "Heavy rain", 10, self.ALL), dynwall.MOODY)
        self.assertIn(dynwall.choose(23, "Rain", 10, self.ALL), dynwall.SLOTS["night"])         # at night rain doesn't change it
        self.assertEqual(dynwall.choose(12, "Clear", 7, self.ALL), dynwall.choose(12, "Clear", 7, self.ALL))   # the same day: the same picture
        self.assertIsNone(dynwall.choose(12, "Clear", 7, set()))

    def test_only_changes_when_the_situation_changes(self):
        with tempfile.TemporaryDirectory() as d:
            pack = d + "/pack"
            os.makedirs(pack)
            for k in self.ALL:
                open(f"{pack}/lennox-{k}.jpg", "w", encoding="utf-8").close()
            dynwall.STATE = d + "/state.json"
            applied = []
            noon = datetime.datetime(2026, 11, 7, 12, 0)
            first = dynwall.check(noon, pack=pack, weather="Clear", apply=applied.append)
            self.assertIsNotNone(first)
            self.assertIsNone(dynwall.check(noon.replace(hour=14), pack=pack, weather="Clear", apply=applied.append))   # still the day
            self.assertEqual(len(applied), 1)
            self.assertIsNotNone(dynwall.check(noon.replace(hour=22), pack=pack, weather="Clear", apply=applied.append))  # night came
            self.assertEqual(len(applied), 2)
            self.assertTrue(applied[0].endswith(f"lennox-{first}.jpg"))
            self.assertIsNone(dynwall.check(noon, pack=d + "/none", weather="Clear", apply=applied.append))               # no pack: nothing


class MusicColors(unittest.TestCase):
    def test_follows_the_music(self):
        st = {}
        self.assertEqual(musiccolors.decide(st, "a.png", "Playing", 100), "theme")
        self.assertIsNone(musiccolors.decide(st, "a.png", "Playing", 130))                 # same cover
        self.assertIsNone(musiccolors.decide(st, "b.png", "Playing", 110))                 # a new cover, but too soon after the last change
        self.assertEqual(musiccolors.decide(st, "b.png", "Playing", 140), "theme")

    def test_pause_keeps_colors_and_the_end_restores_them(self):
        st = {}
        musiccolors.decide(st, "a.png", "Playing", 100)
        self.assertIsNone(musiccolors.decide(st, None, "Paused", 400))                      # a long pause: colors stay
        self.assertIsNone(musiccolors.decide(st, None, "Stopped", 450))                     # just stopped: wait
        self.assertEqual(musiccolors.decide(st, None, "", 450 + musiccolors.RESTORE_AFTER), "restore")
        self.assertIsNone(musiccolors.decide(st, None, "", 900))                            # restored once only

    def test_nothing_playing_never_themes(self):
        self.assertIsNone(musiccolors.decide({}, None, "", 100))
        self.assertIsNone(musiccolors.decide({}, None, "Playing", 100))                      # no cover available


if __name__ == "__main__":
    unittest.main()
