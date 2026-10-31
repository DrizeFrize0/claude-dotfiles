"""Waybar 0.15 Custom::update visibility rules (src/modules/custom.cpp, src/ALabel.cpp)."""
import json, sys
def get_icon(cfg, alt, pct=0):
    fi = cfg.get("format-icons")
    if isinstance(fi, dict):
        fi = fi[alt] if alt and isinstance(fi.get(alt), (str, list)) else fi.get("default")
    if isinstance(fi, list) and fi:
        fi = fi[min(pct // max(1, 100 // len(fi)), len(fi) - 1)]
    return fi if isinstance(fi, str) else ""
def render(cfg, out):
    if not out.strip():
        return None  # hidden: empty output
    d = json.loads(out)
    text, alt = d.get("text", ""), d.get("alt", "")
    s = cfg.get("format", "{text}").format(text=text, alt=alt, icon=get_icon(cfg, alt), percentage=0)
    if (cfg.get("hide-empty-text") and text == "") or s == "":
        return None
    return s
conf = json.load(open(sys.argv[1]))
cases = [
    ("custom/ws7", '{"text": ""}', None, "workspace 7 that doesn't exist"),
    ("custom/ws2", '{"text": "2", "alt": "active", "class": ["ws","active"]}', "show", "active workspace"),
    ("custom/ws3", '{"text": "3", "alt": "empty", "class": ["ws","empty"]}', "show", "empty persistent workspace"),
    ("custom/minimized", '{"text": ""}', None, "nothing minimized"),
    ("custom/minimized", '{"text": "2", "alt": "minimized"}', "show", "2 minimized"),
    ("custom/updates", '{"text": ""}', None, "no updates"),
    ("custom/updates", '{"text": "5", "class": "pending"}', "show", "5 updates"),
    ("custom/gpu", '{"text": ""}', None, "no NVIDIA"),
    ("custom/gpu", '{"text": "󰢮 off"}', "show", "NVIDIA asleep"),
    ("custom/notification", '{"text": "", "alt": "none"}', "show", "bell, no notifications"),
    ("custom/notification", '{"text": "3", "alt": "notification"}', "show", "bell, 3 notifications"),
]
bad = 0
for mod, out, want, what in cases:
    if mod not in conf:
        continue
    got = render(conf[mod], out)
    ok = (got is None) == (want is None)
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {what:32} -> {'hidden' if got is None else repr(got)}")
print("FAILURES:", bad); sys.exit(1 if bad else 0)
