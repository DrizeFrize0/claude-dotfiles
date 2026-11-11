"""Your profile: the name Lennox calls you and your picture, everywhere at once
(login screen, lock screen, the welcome animation, the session screen, the dashboard).

    lennox-profile                       show it
    lennox-profile name "Jado"           what Lennox calls you
    lennox-profile picture FILE          use your own picture (any image; cropped to a square)
    lennox-profile avatar NAME           a painted one: initials, cat, orbit, palm, blocky
    lennox-profile refresh               paint it again (after a theme change, for initials)
    lennox-profile greeting              "Good evening, Jado" (the lock screen shows it)

The picture is saved as ~/.face (and ~/.face.icon, the name the login screen reads),
512 x 512 PNG. The login screen runs as its own user, so the file and your home folder
get a read permission just for it (an ACL; nothing else changes).
"""

import getpass
import json
import math
import os
import pwd
import random
import shutil
import subprocess
import sys
import tempfile
import time

from . import settings as S

HOME = os.path.expanduser("~")
FACE = os.path.join(HOME, ".face")
FACE_ICON = os.path.join(HOME, ".face.icon")
SIZE = 512
AVATARS = {
    "initials": "Your initials on the theme's colors",
    "cat": "A sleepy cat",
    "orbit": "A planet with rings",
    "palm": "A palm at sunset",
    "blocky": "A blocky grass cube",
}


# ---------------------------------------------------------------- the name

def real_name(user=None):
    """The full name from the system account (the GECOS field), if there is one."""
    try:
        gecos = pwd.getpwnam(user or getpass.getuser()).pw_gecos
    except (KeyError, OSError):
        return ""
    return gecos.split(",")[0].strip()


def display_name(settings=None, user=None):
    """Profile name > greeting name > the account's real name > the user name, capitalized."""
    settings = settings or S.load()
    for value in (settings.get("profile", {}).get("name", ""), settings.get("greeting", {}).get("name", ""),
                  real_name(user)):
        if value and value.strip():
            return value.strip()
    return (user or getpass.getuser()).capitalize()


def initials(name):
    parts = [p for p in name.replace("-", " ").split() if p[:1].isalnum()]
    if not parts:
        return "?"
    letters = parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")
    return letters.upper()


# ---------------------------------------------------------------- painting

def _magick():
    for name in ("magick", "convert"):
        if shutil.which(name):
            return name
    return None


def _run(args):
    subprocess.run([_magick()] + [str(a) for a in args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)


def _font(bold=True):
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", "Inter:bold" if bold else "Inter"],
                             capture_output=True, text=True, timeout=5, check=False).stdout.strip()
        return out if out and os.path.exists(out) else None
    except (OSError, subprocess.SubprocessError):
        return None


def _colors():
    try:
        with open(os.path.join(S.CONFIG_DIR, "colors.json"), encoding="utf-8") as f:
            c = json.load(f)
        return c.get("primary", "#81d5cd"), c.get("tertiary", "#afc9e7"), c.get("on_primary", "#003734")
    except (OSError, ValueError):
        return "#81d5cd", "#afc9e7", "#003734"


def paint(kind, out, name="", seed=None):
    """Paint a 512 x 512 avatar into `out` (PNG)."""
    if _magick() is None:
        raise OSError("ImageMagick is missing (sudo pacman -S imagemagick)")
    s = SIZE
    target = "png:" + out           # always PNG, whatever the file is called (~/.face has no extension)
    rnd = random.Random(seed if seed is not None else kind)
    with tempfile.TemporaryDirectory(prefix="lennox-face-") as tmp:
        if kind == "initials":
            a, b, _ = _colors()
            text = initials(name or display_name())
            font = _font()
            big = int(s * 1.5)                 # rotated, then the middle is cut out: no corners show
            _run(["-size", f"{big}x{big}", f"gradient:{a}-{b}", "-rotate", "-35", "+repage", "-gravity", "center",
                  "-crop", f"{s}x{s}+0+0", "+repage",
                  *(["-font", font] if font else []), "-fill", "white", "-pointsize", s * (0.42 if len(text) < 2 else 0.36),
                  "-annotate", "+0+6", text, target])
        elif kind == "cat":
            ears = (f"polygon {s*.25:.0f},{s*.36:.0f} {s*.30:.0f},{s*.14:.0f} {s*.45:.0f},{s*.30:.0f}"
                    f" polygon {s*.75:.0f},{s*.36:.0f} {s*.70:.0f},{s*.14:.0f} {s*.55:.0f},{s*.30:.0f}")
            inner = (f"polygon {s*.29:.0f},{s*.32:.0f} {s*.31:.0f},{s*.20:.0f} {s*.40:.0f},{s*.30:.0f}"
                     f" polygon {s*.71:.0f},{s*.32:.0f} {s*.69:.0f},{s*.20:.0f} {s*.60:.0f},{s*.30:.0f}")
            _run(["-size", f"{s}x{s}", "gradient:#ffd6a5-#ffadad",
                  "-fill", "#3b3355", "-draw", ears, "-draw", f"ellipse {s/2:.0f},{s*.55:.0f} {s*.30:.0f},{s*.26:.0f} 0,360",
                  "-fill", "#ff9eb5", "-draw", inner,
                  # closed sleepy eyes, a nose, whiskers
                  "-fill", "none", "-stroke", "#f6e7c1", "-strokewidth", s * 0.018,
                  "-draw", f"arc {s*.34:.0f},{s*.47:.0f} {s*.46:.0f},{s*.57:.0f} 20,160",
                  "-draw", f"arc {s*.54:.0f},{s*.47:.0f} {s*.66:.0f},{s*.57:.0f} 20,160",
                  "-stroke", "none", "-fill", "#ff9eb5",
                  "-draw", f"polygon {s*.47:.0f},{s*.60:.0f} {s*.53:.0f},{s*.60:.0f} {s*.50:.0f},{s*.64:.0f}",
                  "-fill", "none", "-stroke", "rgba(246,231,193,0.8)", "-strokewidth", s * 0.008,
                  "-draw", f"line {s*.20:.0f},{s*.60:.0f} {s*.38:.0f},{s*.63:.0f}",
                  "-draw", f"line {s*.20:.0f},{s*.68:.0f} {s*.38:.0f},{s*.66:.0f}",
                  "-draw", f"line {s*.80:.0f},{s*.60:.0f} {s*.62:.0f},{s*.63:.0f}",
                  "-draw", f"line {s*.80:.0f},{s*.68:.0f} {s*.62:.0f},{s*.66:.0f}",
                  # a little "z"
                  "-stroke", "#3b3355", "-strokewidth", s * 0.014,
                  "-draw", f"polyline {s*.72:.0f},{s*.12:.0f} {s*.80:.0f},{s*.12:.0f} {s*.72:.0f},{s*.20:.0f} {s*.80:.0f},{s*.20:.0f}",
                  target])
        elif kind == "orbit":
            stars = []
            for _ in range(60):
                x, y, r = rnd.uniform(0, s), rnd.uniform(0, s), rnd.choice((1, 1, 1.5, 2))
                stars += ["-fill", f"rgba(255,255,255,{rnd.uniform(0.4, 1):.2f})", "-draw", f"circle {x:.0f},{y:.0f} {x + r:.1f},{y:.0f}"]
            _run(["-size", f"{s}x{s}", "gradient:#0b0f2e-#2b1b5e", *stars,
                  "-fill", "none", "-stroke", "rgba(190,200,255,0.55)", "-strokewidth", s * 0.02,
                  "-draw", f"ellipse {s/2:.0f},{s*.55:.0f} {s*.40:.0f},{s*.11:.0f} 180,360",
                  "-stroke", "none", "-fill", "#7d6cf0", "-draw", f"circle {s/2:.0f},{s*.55:.0f} {s*.71:.0f},{s*.55:.0f}",
                  "-fill", "rgba(255,255,255,0.18)", "-draw", f"circle {s*.44:.0f},{s*.48:.0f} {s*.52:.0f},{s*.48:.0f}",
                  "-fill", "none", "-stroke", "rgba(190,200,255,0.9)", "-strokewidth", s * 0.02,
                  "-draw", f"ellipse {s/2:.0f},{s*.55:.0f} {s*.40:.0f},{s*.11:.0f} 0,180", target])
        elif kind == "palm":
            _run(["-size", f"{s}x{s//2}", "gradient:#2d1b4e-#ff8a65", f"{tmp}/sky.png"])
            _run(["-size", f"{s}x{s//2}", "gradient:#ff8a65-#5b2a5e", f"{tmp}/sea.png"])
            leaves = []
            tx, ty = s * 0.55, s * 0.36
            for ang in (-165, -135, -105, -75, -45, -15, 12):
                r = math.radians(ang)
                ex, ey = tx + math.cos(r) * s * 0.26, ty + math.sin(r) * s * 0.14 + s * 0.08
                mx, my = tx + math.cos(r) * s * 0.14, ty + math.sin(r) * s * 0.15 - s * 0.05
                leaves += ["-draw", f"path 'M {tx:.0f},{ty:.0f} Q {mx:.0f},{my:.0f} {ex:.0f},{ey:.0f}'"]
            _run([f"{tmp}/sky.png", f"{tmp}/sea.png", "-append",
                  "-fill", "#ffe3a3", "-draw", f"circle {s*.36:.0f},{s*.52:.0f} {s*.50:.0f},{s*.52:.0f}",
                  "-fill", "#1c0f2b", "-draw", f"rectangle 0,{s*.80:.0f} {s},{s}",
                  "-fill", "none", "-stroke", "#1c0f2b", "-strokewidth", s * 0.035,
                  "-draw", f"path 'M {s*.46:.0f},{s*.82:.0f} Q {s*.50:.0f},{s*.55:.0f} {tx:.0f},{ty:.0f}'",
                  "-strokewidth", s * 0.028, *leaves, target])
        elif kind == "blocky":
            px = s // 8
            draws = []
            for row in range(8):
                for col in range(8):
                    if row < 3:
                        color = rnd.choice(("#5fbf4a", "#58b443", "#66c552", "#4fa83c"))
                        if row == 2 and rnd.random() < 0.5:
                            color = rnd.choice(("#8a5a35", "#7f522f"))
                    else:
                        color = rnd.choice(("#8a5a35", "#7f522f", "#94633c", "#76492a"))
                    draws += ["-fill", color, "-draw", f"rectangle {col*px},{row*px} {(col+1)*px-1},{(row+1)*px-1}"]
            _run(["-size", f"{s}x{s}", "xc:#79c6ff", *draws, target])
        else:
            raise ValueError(f"unknown avatar: {kind}")


def from_file(src, out):
    """Any picture -> a centered 512 x 512 square PNG."""
    if _magick() is None:
        raise OSError("ImageMagick is missing (sudo pacman -S imagemagick)")
    _run([src + "[0]", "-auto-orient", "-resize", f"{SIZE}x{SIZE}^", "-gravity", "center",
          "-extent", f"{SIZE}x{SIZE}", "-strip", "png:" + out])


# ---------------------------------------------------------------- saving

def install(png, face=FACE, icon=FACE_ICON, setfacl=True):
    """Put the picture in place for every screen (written in place, so the login screen's
    read permission on the file stays)."""
    with open(png, "rb") as f:
        data = f.read()
    for path in (face, icon):
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o644)
    if setfacl:
        allow_login_screen(icon)


def allow_login_screen(icon=FACE_ICON, home=HOME):
    """SDDM runs as the user "sddm": let it into the home folder (no listing) and read the picture."""
    if not shutil.which("setfacl"):
        return False
    try:
        pwd.getpwnam("sddm")
    except KeyError:
        return False
    ok = True
    for args in (["-m", "u:sddm:x", home], ["-m", "u:sddm:r", icon]):
        ok &= subprocess.run(["setfacl", *args], capture_output=True, timeout=5, check=False).returncode == 0
    return ok


def set_avatar(kind, settings=None):
    settings = settings or S.load()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "face.png")
        paint(kind, out, display_name(settings))
        install(out)
    settings.setdefault("profile", {})["picture"] = kind
    S.save(settings)


def set_picture(src, settings=None):
    settings = settings or S.load()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "face.png")
        from_file(src, out)
        install(out)
    settings.setdefault("profile", {})["picture"] = "custom"
    S.save(settings)


PREVIEWS = os.path.join(S.CACHE_DIR, "avatars")


def previews(folder=PREVIEWS, settings=None):
    """Small copies of every painted avatar, for the picker in Settings > Profile."""
    os.makedirs(folder, exist_ok=True)
    name = display_name(settings)
    out = {}
    for kind in AVATARS:
        path = os.path.join(folder, f"{kind}.png")
        if kind == "initials" or not os.path.exists(path):      # initials follow the name and colors
            paint(kind, path, name)
        out[kind] = path
    return out


def ensure():
    """Paint the default picture once (first login, or the file went missing)."""
    if os.path.exists(FACE) and os.path.exists(FACE_ICON):
        return False
    settings = S.load()
    kind = settings.get("profile", {}).get("picture", "initials")
    if os.path.exists(FACE) and not os.path.exists(FACE_ICON):
        shutil.copyfile(FACE, FACE_ICON)
        allow_login_screen()
        return True
    set_avatar(kind if kind in AVATARS else "initials", settings)
    return True


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "show"
    settings = S.load()
    try:
        if cmd == "show":
            print(f"Name:    {display_name(settings)}")
            print(f"Picture: {settings['profile']['picture']} ({FACE if os.path.exists(FACE) else 'not painted yet'})")
            print("Avatars: " + ", ".join(AVATARS))
        elif cmd == "name" and len(argv) > 2:
            settings["profile"]["name"] = " ".join(argv[2:]).strip()[:40]
            S.save(settings)
            if settings["profile"]["picture"] == "initials":
                set_avatar("initials", settings)
            print(f"Lennox now calls you {display_name(settings)}")
        elif cmd == "picture" and len(argv) > 2:
            set_picture(os.path.expanduser(argv[2]), settings)
            print(f"Picture set from {argv[2]}")
        elif cmd == "avatar" and len(argv) > 2 and argv[2] in AVATARS:
            set_avatar(argv[2], settings)
            print(f"Picture: {argv[2]}")
        elif cmd == "refresh":
            kind = settings["profile"]["picture"]
            if kind in AVATARS:
                set_avatar(kind, settings)
            print("Done")
        elif cmd == "ensure":
            ensure()
        elif cmd == "greeting":
            from . import greeting as G
            print(f"{G.hello(time.localtime().tm_hour)}, {display_name(settings)}")
        elif cmd == "previews":
            for kind, path in previews(settings=settings).items():
                print(f"{kind}\t{path}")
        else:
            print(__doc__.strip(), file=sys.stderr)
            return 2
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print(f"lennox-profile: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
