"""Daily care: prayer times, heat and water logic (no desktop needed)."""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dotfiles", ".local", "share", "lennox", "python"))
from lennox import care  # noqa: E402

AMMAN = (31.95, 35.93, 3)


def put(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def hm(dt):
    return dt.hour + dt.minute / 60


class Prayer(unittest.TestCase):
    def test_order_and_gaps(self):
        for day in (datetime.date(2026, 11, 3), datetime.date(2026, 6, 21), datetime.date(2026, 1, 1)):
            t = care.prayer_times(day, *AMMAN)
            names = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
            self.assertEqual(names, sorted(names, key=lambda n: t[n]), day)
            self.assertTrue(12.0 < hm(t["dhuhr"]) < 12.8, (day, t["dhuhr"]))
            self.assertTrue(2.2 < hm(t["asr"]) - hm(t["dhuhr"]) < 3.8, day)
            self.assertTrue(1.0 < hm(t["sunrise"]) - hm(t["fajr"]) < 1.9, day)
            self.assertTrue(1.0 < hm(t["isha"]) - hm(t["maghrib"]) < 1.9, day)

    def test_seasons(self):
        winter = care.prayer_times(datetime.date(2026, 12, 21), *AMMAN)
        summer = care.prayer_times(datetime.date(2026, 6, 21), *AMMAN)
        self.assertTrue(hm(summer["sunrise"]) < hm(winter["sunrise"]))
        self.assertTrue(hm(summer["maghrib"]) > hm(winter["maghrib"]))
        # Amman midsummer, permanent UTC+3: sunrise about 5:30
        self.assertTrue(5.0 < hm(summer["sunrise"]) < 6.0)

    def test_next(self):
        t = care.prayer_times(datetime.date(2026, 11, 3), *AMMAN)
        name, at = care.next_prayer(t["dhuhr"] - datetime.timedelta(minutes=5), *AMMAN)
        self.assertEqual(name, "dhuhr")
        name, at = care.next_prayer(t["isha"] + datetime.timedelta(minutes=5), *AMMAN)
        self.assertEqual((name, at.date()), ("fajr", datetime.date(2026, 11, 4)))

    def test_polar_does_not_crash(self):
        care.prayer_times(datetime.date(2026, 6, 21), 69.0, 18.0, 2)


class Heat(unittest.TestCase):
    def test_sustained_heat_then_quiet(self):
        h = care.Heat()
        lim = {"CPU": 90}
        n = care.HEAT_STRIKES
        for k in range(n - 1):
            self.assertIsNone(h.look(30 * k, {"CPU": 95}, lim))        # short boosts: no warning yet
        self.assertIn("CPU is at 95", h.look(30 * n, {"CPU": 95}, lim))
        self.assertIsNone(h.look(30 * n + 30, {"CPU": 95}, lim))     # cooldown
        self.assertIn("CPU", h.look(30 * n + care.HEAT_COOLDOWN + 1, {"CPU": 95}, lim))   # still hot after the cooldown: warns again

    def test_a_spike_never_warns(self):
        h = care.Heat()
        lim = {"CPU": 90}
        for t, temp in enumerate((50, 98, 50, 97, 55, 99, 52, 98, 50, 98)):    # up and down: never 4 hot looks in a row
            self.assertIsNone(h.look(t * 30, {"CPU": temp}, lim))

    def test_blip_resets(self):
        h = care.Heat()
        lim = {"CPU": 90}
        for t in range(care.HEAT_STRIKES - 1):
            self.assertIsNone(h.look(t * 30, {"CPU": 95}, lim))
        self.assertIsNone(h.look(300, {"CPU": 60}, lim))               # cooled down: the count starts over
        self.assertIsNone(h.look(330, {"CPU": 95}, lim))

    def test_missing_reading(self):
        self.assertIsNone(care.Heat().look(0, {"CPU": None, "GPU": None}, {"CPU": 90}))

    def test_cpu_temp_reads_hwmon(self):
        with tempfile.TemporaryDirectory() as root:
            for n, name, temp in (("hwmon0", "nvme", "70000"), ("hwmon1", "coretemp", "61000")):
                os.makedirs(os.path.join(root, n))
                put(os.path.join(root, n, "name"), name)
                put(os.path.join(root, n, "temp1_input"), temp)
            self.assertEqual(care.cpu_temp(root), 61.0)
            self.assertIsNone(care.cpu_temp(os.path.join(root, "none")))

    def test_sleeping_nvidia_is_not_woken(self):
        with tempfile.TemporaryDirectory() as root:
            dev = os.path.join(root, "0000:01:00.0")
            os.makedirs(os.path.join(dev, "power"))
            for f, v in (("vendor", "0x10de"), ("class", "0x030000")):
                put(os.path.join(dev, f), v)
            put(os.path.join(dev, "power", "runtime_status"), "suspended")
            self.assertFalse(care.nvidia_awake(root))
            put(os.path.join(dev, "power", "runtime_status"), "active")
            self.assertTrue(care.nvidia_awake(root))


class Water(unittest.TestCase):
    def test_counts_only_active_time(self):
        w = care.Water()
        fired = [w.look(True, 15, step=300) for _ in range(3)]
        self.assertEqual(fired, [False, False, True])
        self.assertFalse(w.look(False, 15, step=900))            # locked or gaming: not counted
        self.assertEqual(w.seconds, 0)


if __name__ == "__main__":
    unittest.main()
