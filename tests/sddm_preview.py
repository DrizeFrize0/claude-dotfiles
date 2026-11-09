"""Load the Lennox Expressive SDDM theme in Qt 6 with stand-ins for SDDM's objects
(sddm, userModel, sessionModel, config, keyboard), drive a wrong and a right password,
and take screenshots. Needs PySide6 (pip install PySide6-Essentials) and a display:
    xvfb-run -a -s "-screen 0 1600x900x24" python3 tests/sddm_preview.py OUT_DIR [USERS]
Prints ok/FAIL lines; any QML warning is a failure."""
import json
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"

from PySide6.QtCore import Property, QObject, Qt, QTimer, QUrl, Signal, Slot, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication, QStandardItem, QStandardItemModel  # noqa: E402
from PySide6.QtQml import QQmlPropertyMap  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(R, "setup", "system", "usr", "share", "sddm", "themes", "lennox-expressive")
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
NUSERS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
os.makedirs(OUT, exist_ok=True)
warnings, fails = [], []


def handler(mode, context, message):
    if "XDG_RUNTIME_DIR" in message or "propagateSizeHints" in message or "nonexistent.png" in message:
        return
    warnings.append(message)
    print("QML:", message, flush=True)


qInstallMessageHandler(handler)


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        fails.append(what)


class Sddm(QObject):
    loginFailed = Signal()
    loginSucceeded = Signal()

    def __init__(self):
        super().__init__()
        self.calls = []

    @Slot(str, str, int)
    def login(self, user, password, session):
        self.calls.append((user, password, session))
        QTimer.singleShot(300, self.loginSucceeded.emit if password == "right" else self.loginFailed.emit)

    @Slot()
    def powerOff(self):
        self.calls.append("poweroff")

    @Slot()
    def reboot(self):
        self.calls.append("reboot")

    @Slot()
    def suspend(self):
        self.calls.append("suspend")

    def _true(self):
        return True

    canPowerOff = Property(bool, _true, constant=True)
    canReboot = Property(bool, _true, constant=True)
    canSuspend = Property(bool, _true, constant=True)
    hostName = Property(str, lambda self: "victus", constant=True)


class Model(QStandardItemModel):
    def __init__(self, roles, rows, last=0):
        super().__init__()
        self._roles = {Qt.UserRole + 1 + i: r.encode() for i, r in enumerate(roles)}
        for row in rows:
            item = QStandardItem()
            for i, r in enumerate(roles):
                item.setData(row.get(r, ""), Qt.UserRole + 1 + i)
            self.appendRow(item)
        self._last = last

    def roleNames(self):
        return self._roles

    lastIndex = Property(int, lambda self: self._last, constant=True)


class Keyboard(QObject):
    capsLock = Property(bool, lambda self: False, constant=True)


# A copy of the theme with a wallpaper, its colors and a face picture
theme = tempfile.mkdtemp()
shutil.copytree(SRC, theme, dirs_exist_ok=True)
os.makedirs(os.path.join(theme, "backgrounds"), exist_ok=True)
os.system(f"convert -size 1600x900 gradient:'#2b1b5e'-'#ff8a65' '{theme}/backgrounds/lennox.jpg'")
json.dump({"primary": "#ffb59a", "on_primary": "#5a1c04", "surface": "#1a110e", "on_surface": "#f1dfd9",
           "surface_container": "#271d1a", "outline": "#a08d86", "error": "#ffb4ab"},
          open(os.path.join(theme, "backgrounds", "colors.json"), "w"))
face = os.path.join(theme, "face.png")
os.system(f"convert -size 256x256 gradient:'#ffd6a5'-'#ffadad' -fill '#3b3355' -draw 'circle 128,140 128,60' '{face}'")

app = QGuiApplication(sys.argv)
sddm = Sddm()
users = [{"name": "jado", "realName": "Jado", "homeDir": "/home/jado", "icon": face, "needsPassword": True}]
users += [{"name": f"guest{i}", "realName": "", "icon": "/nonexistent.png"} for i in range(1, NUSERS)]
user_model = Model(["name", "realName", "homeDir", "icon", "needsPassword"], users)
session_model = Model(["name", "file", "comment"], [{"name": "Lennox (Hyprland)"}, {"name": "Hyprland"}])
config = QQmlPropertyMap(None)
for line in open(os.path.join(theme, "theme.conf")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        config.insert(k, v)
keyboard = Keyboard()

view = QQuickView()
ctx = view.rootContext()
for name, obj in (("sddm", sddm), ("userModel", user_model), ("sessionModel", session_model),
                  ("config", config), ("keyboard", keyboard)):
    ctx.setContextProperty(name, obj)
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.resize(1600, 900)
view.setSource(QUrl.fromLocalFile(os.path.join(theme, "Main.qml")))
check(view.status() == QQuickView.Ready, f"Main.qml loads ({[e.toString() for e in view.errors()]})")
view.show()
root = view.rootObject()


def shot(name):
    view.grabWindow().save(os.path.join(OUT, f"sddm-{name}.png"))


def find(name):
    return root.findChild(QObject, name) if root else None


steps = []


def at(ms, fn):
    steps.append((ms, fn))


def type_password(text):
    item = root.findChild(QObject, "password") if root else None
    return item


at(120, lambda: shot("opening"))
at(1900, lambda: (shot("ready"),
                  check(abs(float(root.property("width")) - 1600) < 1, "fills the screen"),
                  check(str(root.property("primary").name()) == "#ffb59a", "wallpaper colors loaded from colors.json")))


def wrong():
    root.setProperty("busy", False)
    pw = root.findChild(QObject, "password")
    check(pw is not None, "the password field")
    pw.setProperty("text", "wrong")
    root.metaObject()  # noqa
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(root, "login")


at(2100, wrong)
at(2500, lambda: (shot("wrong"), check(sddm.calls and sddm.calls[-1] == ("jado", "wrong", 0), f"login called with the user and session ({sddm.calls})")))


def right():
    pw = root.findChild(QObject, "password")
    check(pw.property("text") == "", "the field is emptied after a wrong password")
    pw.setProperty("text", "right")
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(root, "login")


at(3000, right)
at(3500, lambda: shot("leaving"))
at(4300, lambda: (shot("left"), check(len(warnings) == 0, f"no QML warnings ({len(warnings)})"),
                  check("Lennox" not in str(sddm.calls[-1]) and sddm.calls[-1][1] == "right", "the right password logs in"),
                  view.setSource(QUrl()), app.quit()))

for ms, fn in steps:
    QTimer.singleShot(ms, fn)
app.exec()
print("FAILED: %d" % len(fails) if fails else "OK sddm-theme", flush=True)
sys.exit(1 if fails else 0)
