"""Per-app GPU choice. Run: python3 tests/test_gpuapps.py"""
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ.update(HOME=T, XDG_STATE_HOME=os.path.join(T, "state"), XDG_DATA_HOME=os.path.join(T, "data"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dotfiles", ".local", "share",
                                "lennox", "python"))
from lennox import gpuapps as G  # noqa: E402

fails = []


def check(c, what):
    print(("ok   " if c else "FAIL ") + what)
    c or fails.append(what)


sysd, user, orig = os.path.join(T, "sys"), os.path.join(T, "user"), os.path.join(T, "orig")
os.makedirs(sysd)
open(os.path.join(sysd, "blender.desktop"), "w").write(
    "[Desktop Entry]\nType=Application\nName=Blender\nExec=blender %f\n\n[Desktop Action new]\nName=New\nExec=blender --new\n")
open(os.path.join(sysd, "hidden.desktop"), "w").write("[Desktop Entry]\nType=Application\nName=H\nExec=h\nNoDisplay=true\n")
open(os.path.join(sysd, "link.desktop"), "w").write("[Desktop Entry]\nType=Link\nName=L\nURL=x\n")
kw = {"dirs": [sysd], "user_dir": user}

check([a["id"] for a in G.apps(**kw)] == ["blender.desktop"], "hidden entries and links are not listed")
ok, msg = G.pin("blender", orig_dir=orig, **kw)
text = open(os.path.join(user, "blender.desktop")).read()
check(ok and "Exec=lennox-gpu run blender %f" in text and "Exec=lennox-gpu run blender --new" in text,
      "pin puts the GPU launcher in front of every command (app and actions)")
check(text.count(G.MARK) == 1 and text.splitlines()[0] == "[Desktop Entry]" and text.splitlines()[1] == G.MARK,
      "the marker sits right under [Desktop Entry]")
check(G.apps(**kw)[0]["pinned"], "the list shows it pinned")
ok, msg = G.pin("blender.desktop", orig_dir=orig, **kw)
check("already" in msg and open(os.path.join(user, "blender.desktop")).read().count("lennox-gpu run") == 2, "pinning twice changes nothing")
ok, msg = G.unpin("blender", user_dir=user, orig_dir=orig)
check(ok and not os.path.exists(os.path.join(user, "blender.desktop")), "unpin removes our copy")
ok, msg = G.unpin("blender", user_dir=user, orig_dir=orig)
check(not ok, "unpinning an unpinned app says so")
ok, msg = G.pin("nothing", orig_dir=orig, **kw)
check(not ok and "No app" in msg, "unknown app")

# your own entry is kept and comes back
os.makedirs(user, exist_ok=True)
mine = "[Desktop Entry]\nType=Application\nName=Blender mine\nExec=blender --my-flag\n"
open(os.path.join(user, "blender.desktop"), "w").write(mine)
G.pin("blender", orig_dir=orig, **kw)
check("lennox-gpu run blender --my-flag" in open(os.path.join(user, "blender.desktop")).read(), "your own entry is the one that gets pinned")
G.unpin("blender", user_dir=user, orig_dir=orig)
check(open(os.path.join(user, "blender.desktop")).read() == mine, "and unpinning puts it back as it was")
print("OK gpuapps" if not fails else "FAILED gpuapps: %d" % len(fails))
sys.exit(1 if fails else 0)
