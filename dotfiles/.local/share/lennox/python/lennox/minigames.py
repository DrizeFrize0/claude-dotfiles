"""Mini-games for a quick break: Snake and Flappy.

    python3 -m lennox.minigames snake|flappy|menu

Arrow keys or WASD move (Space or Up flaps), R restarts, Esc closes.
"""

import random
import subprocess
import sys
from collections import deque

SIZE = 420


class Snake:
    """A grid game: eat the dots, don't hit a wall or yourself."""

    DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

    def __init__(self, cols=20, rows=20, rng=random):
        self.cols, self.rows, self.rng = cols, rows, rng
        self.body = deque([(cols // 2 - i, rows // 2) for i in range(3)])
        self.dir, self.queued, self.alive = (1, 0), None, True
        self.food = self._place()

    def _place(self):
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in self.body]
        return self.rng.choice(free) if free else None

    @property
    def score(self):
        return len(self.body) - 3

    def turn(self, name):
        d = self.DIRS[name]
        current = self.queued or self.dir
        if (d[0] + current[0], d[1] + current[1]) != (0, 0):          # no turning back on yourself
            self.queued = d

    def step(self):
        if not self.alive:
            return False
        if self.queued:
            self.dir, self.queued = self.queued, None
        hx, hy = self.body[0]
        head = (hx + self.dir[0], hy + self.dir[1])
        eating = head == self.food
        tail = None if eating else self.body[-1]
        if not (0 <= head[0] < self.cols and 0 <= head[1] < self.rows) or (head in self.body and head != tail):
            self.alive = False
            return False
        self.body.appendleft(head)
        if eating:
            self.food = self._place()
            if self.food is None:
                self.alive = False
        else:
            self.body.pop()
        return self.alive


class Flappy:
    """Tap to flap through the gaps."""

    GRAVITY, FLAP, SPEED, GAP, PIPE_W, EVERY = 1500.0, -430.0, 170.0, 130.0, 54.0, 220.0

    def __init__(self, width=SIZE, height=SIZE, rng=random):
        self.w, self.h, self.rng = width, height, rng
        self.y, self.vy, self.x = height / 2, 0.0, width * 0.28
        self.pipes, self.since, self.score, self.alive = [], self.EVERY, 0, True

    def flap(self):
        if self.alive:
            self.vy = self.FLAP

    def step(self, dt):
        if not self.alive:
            return False
        self.vy += self.GRAVITY * dt
        self.y += self.vy * dt
        self.since += self.SPEED * dt
        if self.since >= self.EVERY:
            self.since = 0.0
            self.pipes.append({"x": float(self.w), "gap": self.rng.uniform(90, self.h - 90 - self.GAP), "scored": False})
        for p in self.pipes:
            p["x"] -= self.SPEED * dt
            if not p["scored"] and p["x"] + self.PIPE_W < self.x:
                p["scored"] = True
                self.score += 1
        self.pipes = [p for p in self.pipes if p["x"] > -self.PIPE_W]
        if self.y < 0 or self.y > self.h - 8:
            self.alive = False
        for p in self.pipes:
            if p["x"] < self.x + 8 and self.x - 8 < p["x"] + self.PIPE_W and not (p["gap"] < self.y - 8 and self.y + 8 < p["gap"] + self.GAP):
                self.alive = False
        return self.alive


def window_main(kind):
    from . import achievements
    from . import overlay as O
    Gtk, Gdk = O.Gtk, O.Gdk

    class Game(Gtk.Window):
        def __init__(self):
            super().__init__(title=f"Lennox {kind}", decorated=False)
            self.set_default_size(SIZE, SIZE)
            self.add_css_class("lennox-overlay")
            O.css("window.lennox-overlay { background: rgba(14,16,26,0.96); border-radius: 18px; } "
                  "label.game-score { color: white; font-weight: bold; font-size: 15px; margin: 12px 16px; }")
            self.new_game()
            self.canvas = O.Canvas(self.draw, self.tick, fps=60)
            self.score_label = Gtk.Label(label="", halign=Gtk.Align.START, valign=Gtk.Align.START, css_classes=["game-score"])
            overlay = Gtk.Overlay(child=self.canvas)
            overlay.add_overlay(self.score_label)
            self.set_child(overlay)
            O.configure(self, "lennox-game", "overlay", "exclusive", anchors=())
            keys = Gtk.EventControllerKey()
            keys.connect("key-pressed", self.key)
            self.add_controller(keys)
            click = Gtk.GestureClick()
            click.connect("pressed", lambda *_a: self.flap())
            self.add_controller(click)
            self.canvas.start()

        def new_game(self):
            self.game = Snake() if kind == "snake" else Flappy()
            self.acc, self.saved, self.started = 0.0, False, False

        def flap(self):
            if kind == "flappy":
                self.started = True
                self.game.flap()

        def key(self, _c, keyval, _code, _state):
            name = Gdk.keyval_name(keyval).lower()
            if name == "escape":
                self.close()
            elif name == "r":
                self.new_game()
            elif kind == "snake":
                turn = {"up": "up", "w": "up", "down": "down", "s": "down", "left": "left", "a": "left", "right": "right", "d": "right"}
                if name in turn:
                    self.started = True
                    self.game.turn(turn[name])
            elif name in ("space", "up", "w"):
                self.flap()
            return True

        def tick(self, dt, _w, _h):
            g = self.game
            if not self.started:
                self.score_label.set_label("Press " + ("an arrow key" if kind == "snake" else "Space") + " to start")
                return
            if kind == "snake":
                self.acc += dt
                while self.acc >= 0.11:
                    self.acc -= 0.11
                    g.step()
            else:
                g.step(dt)
            self.score_label.set_label(f"{g.score}" + ("   Game over: R to retry, Esc to close" if not g.alive else ""))
            if not g.alive and not self.saved:
                self.saved = True
                achievements.tick(f"{kind}_best", g.score, best=True)

        def draw(self, snap, w, h):
            r, gr, b = O.accent()
            g = self.game
            if kind == "snake":
                cell = min(w / g.cols, h / g.rows)
                for i, (x, y) in enumerate(g.body):
                    O.fill(snap, x * cell + 1, y * cell + 1, cell - 2, cell - 2, O.rgba(r, gr, b, 1.0 if i == 0 else 0.75), cell * 0.3)
                if g.food:
                    O.disc(snap, (g.food[0] + 0.5) * cell, (g.food[1] + 0.5) * cell, cell * 0.32, O.rgba(1, 0.45, 0.45))
            else:
                for p in g.pipes:
                    O.fill(snap, p["x"], 0, g.PIPE_W, p["gap"], O.rgba(0.35, 0.8, 0.5), 8)
                    O.fill(snap, p["x"], p["gap"] + g.GAP, g.PIPE_W, h - p["gap"] - g.GAP, O.rgba(0.35, 0.8, 0.5), 8)
                O.disc(snap, g.x, g.y, 11, O.rgba(r, gr, b))
                O.disc(snap, g.x + 4, g.y - 3, 2, O.rgba(0, 0, 0, 0.8))

    app = Gtk.Application(application_id="dev.lennox.Game")
    app.connect("activate", lambda a: (Game().set_application(a), a.get_windows()[0].present()))
    return app.run([])


def main(argv):
    mode = argv[1] if len(argv) > 1 else "menu"
    if mode == "menu":
        pick = subprocess.run(["rofi", "-dmenu", "-p", "Play"], input="snake\nflappy\n", capture_output=True, text=True, check=False).stdout.strip()
        mode = pick if pick in ("snake", "flappy") else ""
        if not mode:
            return 0
    if mode in ("snake", "flappy"):
        return window_main(mode)
    print("usage: lennox-minigame snake | flappy | menu", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
