"""The tour. Run: xvfb-run -a -s "-screen 0 1280x720x24" /usr/bin/python3.12 tests/test_tour.py [SHOT_DIR]"""
import os
import subprocess
import sys
import tempfile
import time

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_RUNTIME_DIR=os.path.join(T, "run"), XDG_CONFIG_HOME=os.path.join(T, ".config"),
                  XDG_STATE_HOME=os.path.join(T, "state"), GDK_BACKEND="x11", GSK_RENDERER="cairo", NO_AT_BRIDGE="1",
                  LENNOX_WIDGETS_NO_LAYER="1")
os.makedirs(os.path.join(T, "run"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import tour as TR, whatsnew as W  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what, flush=True)
    c or fails.append(what)


entries = [{"version": "2.3.0", "date": "", "title": "Safe and sound", "items": ["Restore points", "Self-heal"]},
           {"version": "2.2.2", "date": "", "title": "Checks everything", "items": ["60 sites"]},
           {"version": "2.2.1", "date": "", "title": "Old", "items": ["old thing"]}]
pg = TR.pages(entries, "Jad", "2.2.1")
check([p["id"] for p in pg] == ["welcome", "find", "yours", "safe", "school", "play", "news"], "seven pages, news last")
check(pg[0]["title"] == "Welcome, Jad", "the welcome uses your name")
news = pg[-1]["tips"]
check(any("Restore points" == t["what"] for t in news) and any("60 sites" == t["what"] for t in news)
      and not any("old thing" == t["what"] for t in news), "what's new lists only versions newer than the one you saw")
check(TR.pages(entries, "x", "2.3.0")[-1]["body"] == "You are up to date.", "nothing new: says so")
check(len(TR.pages([], "x", None)) == 7, "no changelog still works")
check(TR.short("One. Two. Three") == "One" and len(TR.short("word " * 60)) <= 111 and TR.short("short") == "short", "changelog items are shortened")
check(all(p["title"] and p["body"] for p in pg), "every page has a title and text")
for p in pg:
    if p["action"]:
        cmd = p["action"][1].split()[0]
        check(cmd in ("lennox-palette", "lennox-settings", "kitty"), f"{p['id']}: the button runs a Lennox command")

check(not TR.seen_tour(), "not seen at first")
TR.mark_done()
check(TR.seen_tour() and TR.main(["x", "first"]) == TR.SHOWN_BEFORE, "after it is done, 'first' shows nothing (exit 10)")
os.remove(TR.DONE)

app, holder = TR.run_window(0, dry=True)
app.register(None)
app.activate()
win = holder["win"]
from lennox import overlay as O  # noqa: E402
ctx = O.GLib.MainContext.default()


def pump(s):
    end = time.time() + s
    while time.time() < end:
        ctx.iteration(False)
        time.sleep(0.01)


pump(0.3)
check(win.index == 0 and not win.back.get_visible() and win.next.get_label() == "Next", "starts on page one, no Back")
win.go(1)
pump(0.1)
check(win.index == 1 and win.back.get_visible() and win.stack.get_visible_child_name() == "find", "Next moves on")
check(sum(1 for d in win.dot_list if d.has_css_class("on")) == 1 and win.dot_list[1].has_css_class("on"), "one dot is lit: the current page")
win.go(-1)
check(win.index == 0, "Back goes back")
win.go(-1)
check(win.index == 0, "Back on page one stays")
for _ in range(6):
    win.go(1)
pump(0.1)
check(win.index == 6 and win.next.get_label() == "Done" and win.stack.get_visible_child_name() == "news", "the last page says Done")
if SHOTS:
    subprocess.run(["import", "-window", "root", "-crop", "800x600+0+0", os.path.join(SHOTS, "tour-news.png")], check=False)
win.launch("lennox-palette")
check(win.launched == ["lennox-palette"], "an action button launches its command (dry run: recorded)")
win.show_page(3, animate=False)
if SHOTS:
    pump(0.2)
    subprocess.run(["import", "-window", "root", "-crop", "800x600+0+0", os.path.join(SHOTS, "tour-safe.png")], check=False)
win.go(1)
win.go(1)
win.go(1)
check(win.index == 6, "navigation by index works")
win.go(1)
print("OK tour" if not fails else "FAILED tour: %d" % len(fails))
sys.exit(1 if fails else 0)
