"""Fake Hyprland: socket1 answers j/monitors, j/workspaces, j/clients; socket2 streams events from a script."""
import json, os, socket, sys, threading, time
base = os.path.join(os.environ["XDG_RUNTIME_DIR"], "hypr", "FAKE")
os.makedirs(base, exist_ok=True)
state = {"focused": 1, "other": None, "ws": {1: 2, 2: 0}, "clients": [{"address": "0xabc", "workspace": {"id": 3}}]}
def s1():
    srv = socket.socket(socket.AF_UNIX); p = os.path.join(base, ".socket.sock")
    if os.path.exists(p): os.unlink(p)
    srv.bind(p); srv.listen(8)
    while True:
        c, _ = srv.accept(); req = c.recv(1024).decode()
        if req == "j/monitors":
            mons = [{"name": "eDP-1", "focused": True, "activeWorkspace": {"id": state["focused"]}}]
            if state["other"]: mons.append({"name": "HDMI-A-1", "focused": False, "activeWorkspace": {"id": state["other"]}})
            out = json.dumps(mons)
        elif req == "j/workspaces":
            out = json.dumps([{"id": k, "name": str(k), "windows": v} for k, v in state["ws"].items()])
        elif req == "j/clients":
            out = json.dumps(state["clients"])
        else:
            out = "unknown"
        c.sendall(out.encode()); c.close()
threading.Thread(target=s1, daemon=True).start()
srv2 = socket.socket(socket.AF_UNIX); p2 = os.path.join(base, ".socket2.sock")
if os.path.exists(p2): os.unlink(p2)
srv2.bind(p2); srv2.listen(1)
conn, _ = srv2.accept()
def emit(e): conn.sendall((e + "\n").encode()); time.sleep(0.4)
time.sleep(0.5)
state["focused"] = 2; state["ws"][2] = 1; emit("workspacev2>>2,2")                  # switch to 2
state["ws"][7] = 1; emit("createworkspacev2>>7,7")                                  # 7 appears
state["ws"][3] = 1; emit("openwindow>>abc,3,kitty,t"); emit("urgent>>abc")         # urgent on 3
state["other"] = 5; emit("focusedmonv2>>HDMI-A-1,5"); emit("monitoraddedv2>>2,HDMI-A-1,x")
for i in range(5): emit("activewindowv2>>abc")                                      # irrelevant noise
time.sleep(1); conn.close(); time.sleep(0.5)
