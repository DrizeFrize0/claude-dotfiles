"""Release 1.26 logic: storage, auto profiles, downloads, Discord, mood report, seasons, trophies, lyrics, games, ask."""
import datetime
import http.server
import json
import os
import random
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import (achievements, ask, autoprofile, discordwidget, downloads, lyrics, minigames,  # noqa: E402
                    mood, seasons, storage)


def touch(path, size=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * size)


class Storage(unittest.TestCase):
    def test_scan_sorts_and_protects(self):
        with tempfile.TemporaryDirectory() as home:
            old = storage.HOME
            storage.HOME = os.path.realpath(home)
            try:
                touch(home + "/Videos/big.bin", 400_000)
                touch(home + "/Documents/small.txt", 10)
                touch(home + "/.config/app/x", 100)
                data = storage.scan(home)
                names = [i["name"] for i in data["items"]]
                self.assertEqual(names[0], "Videos")
                self.assertTrue(next(i for i in data["items"] if i["name"] == "Videos")["safe"])
                self.assertFalse(next(i for i in data["items"] if i["name"] == ".config")["safe"])
                self.assertFalse(storage.can_trash(home))
                self.assertFalse(storage.can_trash("/etc/passwd"))
                self.assertEqual(storage.trash("/etc/passwd"), 1)
                self.assertEqual(storage.trash(home + "/.ssh"), 1)
            finally:
                storage.HOME = old

    def test_human(self):
        self.assertEqual(storage.human(512), "512 B")
        self.assertEqual(storage.human(5 * 1024 ** 2), "5.0 MB")


class AutoProfile(unittest.TestCase):
    def test_parse(self):
        r = autoprofile.parse_rule("wifi:School Wi-Fi -> quiet dnd volume=20")
        self.assertEqual(r, {"when": "wifi", "value": "School Wi-Fi", "perf": "quiet", "dnd": True, "volume": 20})
        self.assertEqual(autoprofile.parse_rule("time:22:00-06:00 -> night=on")["night"], "on")
        for bad in ("wifi: -> quiet", "time:25:00-06:00 -> quiet", "wifi:X -> bogus", "wifi:X", "hello"):
            self.assertIsNone(autoprofile.parse_rule(bad), bad)

    def test_match_time_wraps_midnight(self):
        rules = [autoprofile.parse_rule("time:22:00-06:00 -> quiet"), autoprofile.parse_rule("wifi:Home -> max")]
        self.assertEqual(autoprofile.match(rules, "", 23 * 60)["perf"], "quiet")
        self.assertEqual(autoprofile.match(rules, "", 3 * 60)["perf"], "quiet")
        self.assertIsNone(autoprofile.match(rules, "", 12 * 60))
        self.assertEqual(autoprofile.match(rules, "home", 12 * 60)["perf"], "max")          # not case sensitive
        self.assertEqual(autoprofile.match(rules, "Home", 23 * 60)["perf"], "quiet")        # first rule wins

    def test_decide(self):
        rule = {"when": "wifi", "value": "A"}
        self.assertEqual(autoprofile.decide(None, rule), "apply")
        self.assertEqual(autoprofile.decide({"rule": rule}, rule), None)
        self.assertEqual(autoprofile.decide({"rule": rule}, {"when": "wifi", "value": "B"}), "switch")
        self.assertEqual(autoprofile.decide({"rule": rule}, None), "undo")

    def test_rules_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/r.json"
            autoprofile.save_rules([autoprofile.parse_rule("wifi:A -> quiet")], path)
            self.assertEqual(len(autoprofile.load_rules(path)), 1)
            self.assertEqual(autoprofile.load_rules(d + "/none.json"), [])


class Downloads(unittest.TestCase):
    def test_progress_then_finished(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d + "/movie.mp4.crdownload", 5_000_000)
            now = 1000.0
            state, done = downloads.step({}, downloads.partials(d), d, now)
            self.assertEqual(done, [])
            self.assertIn("5 MB", downloads.bar(state, now)["text"])
            os.rename(d + "/movie.mp4.crdownload", d + "/movie.mp4")
            state, done = downloads.step(state, downloads.partials(d), d, now + 5)
            self.assertEqual(done, [d + "/movie.mp4"])
            self.assertTrue(downloads.bar(state, now + 6)["text"].startswith("󰄬 movie.mp4"))
            self.assertEqual(downloads.bar(state, now + 200)["text"], "")                     # shown for a minute only


class Discord(unittest.TestCase):
    def test_parse_and_cache(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {"name": "Astral", "presence_count": 7, "members": [{"username": "a"}, {"username": "b"}]}
        with tempfile.TemporaryDirectory() as d:
            discordwidget.CACHE = d + "/c.json"
            r = discordwidget.status("123456", now=100, fetch=fetch)
            self.assertEqual((r["ok"], r["online"], r["names"]), (True, 7, ["a", "b"]))
            discordwidget.status("123456", now=150, fetch=fetch)
            self.assertEqual(len(calls), 1)                                                   # cached for two minutes
            self.assertFalse(discordwidget.status("abc", fetch=fetch)["ok"])
            self.assertTrue(discordwidget.status("123456", now=500, fetch=lambda u: 1 / 0 if False else (_ for _ in ()).throw(OSError()))["ok"])


class Mood(unittest.TestCase):
    def test_not_enough_data(self):
        self.assertIn("Keep going", mood.insights({"2026-11-01": 4}, {}, {})[0])

    def test_late_nights_hurt(self):
        moods, nights = {}, {}
        start = datetime.date(2026, 10, 1)
        for i in range(14):
            day = start + datetime.timedelta(days=i)
            late = i % 2 == 0
            nights[day.isoformat()] = "02:30" if late else "23:00"
            moods[(day + datetime.timedelta(days=1)).isoformat()] = 2 if late else 4
        tips = mood.insights(moods, nights, {})
        self.assertTrue(any("late night" in t and "worse" in t for t in tips), tips)

    def test_focus_helps(self):
        moods = {f"2026-10-{d:02d}": (5 if d % 2 else 2) for d in range(1, 11)}
        focus = {f"2026-10-{d:02d}": (90 if d % 2 else 0) for d in range(1, 11)}
        self.assertTrue(any("focus" in t for t in mood.insights(moods, {}, focus)))

    def test_save_and_week(self):
        with tempfile.TemporaryDirectory() as d:
            mood.MOOD = d + "/m.json"
            mood.set_today(4, now=1_000_000)
            self.assertEqual(mood.load()[mood.today(1_000_000)], 4)
            w = mood.week(mood.load(), now=1_000_000)
            self.assertEqual((len(w), w[-1]["mood"]), (7, 4))


class Seasons(unittest.TestCase):
    def test_islamic_dates(self):
        self.assertEqual(seasons.occasions(datetime.date(2026, 2, 19)), ["ramadan"])
        self.assertEqual(seasons.occasions(datetime.date(2026, 2, 10)), [])
        self.assertEqual(seasons.occasions(datetime.date(2026, 3, 21)), ["eid"])
        self.assertIn("eid", seasons.occasions(datetime.date(2026, 5, 27)))                   # Eid al-Adha
        self.assertEqual(seasons.hijri(datetime.date(2026, 11, 3))[0], 1448)

    def test_fixed_days_and_pick(self):
        self.assertEqual(seasons.occasions(datetime.date(2026, 10, 31)), ["halloween"])
        self.assertEqual(seasons.occasions(datetime.date(2026, 12, 31)), ["newyear"])
        self.assertEqual(seasons.occasions(datetime.date(2026, 5, 25)), ["jordan_day"])
        self.assertIsNone(seasons.pick(datetime.date(2026, 10, 31), {"ramadan": True}))
        self.assertEqual(seasons.pick(datetime.date(2026, 10, 31), {"halloween": True}), "halloween")


class Trophies(unittest.TestCase):
    def test_evaluate(self):
        out = {t["id"]: t for t in achievements.evaluate({"focus_sessions": 1, "focus_hours": 4, "overview": 100})}
        self.assertTrue(out["first_focus"]["done"] and out["overview_100"]["done"])
        self.assertFalse(out["focus_10h"]["done"])
        self.assertEqual(out["focus_10h"]["have"], 4)

    def test_ticks(self):
        with tempfile.TemporaryDirectory() as d:
            achievements.COUNTS = d + "/c.json"
            achievements.tick("ocr")
            achievements.tick("ocr")
            achievements.tick("snake_best", 12, best=True)
            achievements.tick("snake_best", 8, best=True)
            data = achievements._json(achievements.COUNTS, {})
            self.assertEqual((data["ocr"], data["snake_best"]), (2, 12))


class Lyrics(unittest.TestCase):
    LRC = "[00:01.00] one\n[00:05.50] اثنان\n[00:09.00]\n[00:12.00] four"

    def test_parse_and_lookup(self):
        p = lyrics.parse_lrc(self.LRC)
        self.assertEqual(lyrics.line_at(p, 0.5), "")
        self.assertEqual(lyrics.line_at(p, 2), "one")
        self.assertEqual(lyrics.line_at(p, 6), "اثنان")
        self.assertEqual(lyrics.line_at(p, 10), "")
        self.assertEqual(lyrics.line_at(p, 99), "four")

    def test_cache(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            def fetch(a, t, n):
                calls.append(t)
                return self.LRC
            lyrics.get("A", "T", 200, fetch, d)
            lyrics.get("A", "T", 200, fetch, d)
            self.assertEqual(len(calls), 1)
            self.assertEqual(lyrics.get("A", "X", 1, lambda *a: (_ for _ in ()).throw(OSError()), d), ([], []))


class Games(unittest.TestCase):
    def test_snake(self):
        s = minigames.Snake(10, 10, random.Random(1))
        s.food = (s.body[0][0] + 1, s.body[0][1])
        self.assertTrue(s.step())
        self.assertEqual(s.score, 1)
        s.turn("left")                                                                      # can't reverse into itself
        s.step()
        self.assertEqual(s.dir, (1, 0))
        for _ in range(20):
            s.step()
        self.assertFalse(s.alive)

    def test_snake_hits_itself(self):
        s = minigames.Snake(10, 10, random.Random(2))
        s.body = minigames.deque([(5, 5), (5, 6), (4, 6), (4, 5), (4, 4), (5, 4)])
        s.dir, s.food = (0, -1), (0, 0)
        s.turn("right")
        self.assertTrue(s.step())

    def test_flappy(self):
        f = minigames.Flappy(rng=random.Random(3))
        for _ in range(200):
            f.step(0.016)
        self.assertFalse(f.alive)                                                           # gravity wins without flaps
        g = minigames.Flappy(rng=random.Random(3))
        for i in range(400):
            if g.vy > 120 and g.y > g.h * 0.5:
                g.flap()
            g.step(0.016)
            if not g.alive:
                break
        self.assertGreaterEqual(g.score, 0)


class Ask(unittest.TestCase):
    def test_api_round_trip(self):
        seen = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["key"] = self.headers["x-api-key"]
                seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
                code = 401 if seen["key"] == "bad" else 200
                self.send_response(code)
                self.end_headers()
                if code == 200:
                    self.wfile.write(json.dumps({"content": [{"type": "text", "text": "Four."}]}).encode())

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_port}/v1/messages"
        try:
            self.assertEqual(ask.ask_api("2+2?", "claude-haiku-5-5", "k", url), "Four.")
            self.assertEqual((seen["key"], seen["body"]["model"], seen["body"]["messages"][0]["content"]), ("k", "claude-haiku-5-5", "2+2?"))
            with self.assertRaises(RuntimeError) as cm:
                ask.ask_api("x", "m", "bad", url)
            self.assertIn("refused", str(cm.exception))
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
