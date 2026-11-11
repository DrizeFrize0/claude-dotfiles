"""Fake Hyprland for minimize: windows move on and off special:minimized."""
import json, os, socket, threading, time
base = os.path.join(os.environ["XDG_RUNTIME_DIR"], "hypr", "FAKE")
os.makedirs(base, exist_ok=True)
state = {"min": 0}
def s1():
    srv = socket.socket(socket.AF_UNIX); p = os.path.join(base, ".socket.sock")
    if os.path.exists(p): os.unlink(p)
    srv.bind(p); srv.listen(8)
    while True:
        c, _ = srv.accept(); req = c.recv(1024).decode()
        if req == "j/monitors":
            out = json.dumps([{"name": "eDP-1", "focused": True, "activeWorkspace": {"id": 1}}])
        elif req == "j/workspaces":
            ws = [{"id": 1, "name": "1", "windows": 1}]
            if state["min"]:
                ws.append({"id": -98, "name": "special:minimized", "windows": state["min"]})
            out = json.dumps(ws)
        else:
            out = "[]"
        c.sendall(out.encode()); c.close()
threading.Thread(target=s1, daemon=True).start()
srv2 = socket.socket(socket.AF_UNIX); p2 = os.path.join(base, ".socket2.sock")
if os.path.exists(p2): os.unlink(p2)
srv2.bind(p2); srv2.listen(1)
conn, _ = srv2.accept()
log = open(os.environ["MINLOG"], "a")
def step(n, event):
    state["min"] = n; conn.sendall((event + "\n").encode()); time.sleep(0.5)
    path = os.path.join(os.environ["XDG_RUNTIME_DIR"], "lennox", "ws", "minimized.json")
    log.write(f"min={n} -> {open(path).read().strip() if os.path.exists(path) else 'NO FILE'}\n"); log.flush()
time.sleep(0.6)
step(1, "movewindowv2>>abc,-98,special:minimized")
step(2, "movewindowv2>>def,-98,special:minimized")
step(1, "movewindowv2>>abc,1,1")
step(0, "closewindow>>def")
conn.close(); time.sleep(0.3)
