#!/usr/bin/env bash
# The Rust fast path: quiet answers are instant, anything else goes to Python. Run: bash tests/test_fast.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v cargo >/dev/null || { echo "skip (no cargo)"; exit 0; }
cargo build --release -q --manifest-path "$SP/../rust/lennox-fast/Cargo.toml" || { echo "FAIL build"; exit 1; }
B="$SP/../rust/lennox-fast/target/release/lennox-fast"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"; export HOME="$T/h" XDG_RUNTIME_DIR="$T/r"
unset XDG_CONFIG_HOME XDG_STATE_HOME
mkdir -p "$HOME/Downloads" "$HOME/.config/lennox" "$HOME/.local/state/lennox" "$XDG_RUNTIME_DIR/lennox" "$HOME/.local/share/lennox"
ln -s "$SP/../dotfiles/.local/share/lennox/python" "$HOME/.local/share/lennox/python"
check "downloads: nothing going on is empty" '[ "$($B downloads waybar)" = "{\"text\": \"\"}" ]'
touch "$HOME/Downloads/f.crdownload"
check "downloads: a partial file goes to Python (active)" '$B downloads waybar | grep -q "\"active\""'
rm "$HOME/Downloads/f.crdownload"
echo '{"partials": {}, "last": "/x/a.zip", "last_time": '"$(date +%s)"'}' > "$XDG_RUNTIME_DIR/lennox/downloads.json"
check "downloads: just finished goes to Python (done)" '$B downloads waybar | grep -q "\"done\""'
echo '{"partials": {}, "last": "/x/a.zip", "last_time": 10}' > "$XDG_RUNTIME_DIR/lennox/downloads.json"
check "downloads: old finish is empty" '[ "$($B downloads waybar)" = "{\"text\": \"\"}" ]'
echo '{"downloads": {"on": false, "folder": ""}}' > "$HOME/.config/lennox/settings.json"
touch "$HOME/Downloads/f.part"
check "downloads: switched off stays empty" '[ "$($B downloads waybar)" = "{\"text\": \"\"}" ]'
check "clock: no data is empty" '[ "$($B clock waybar)" = "{\"text\": \"\"}" ]'
python3 - <<P
import json,time
json.dump({"timers":[{"id":"t1","label":"tea","end":time.time()+300,"paused_left":None}],"alarms":[],"reminders":[],"ringing":[],"stopwatch":{"start":None,"elapsed":0.0,"laps":[]}},open("$HOME/.local/state/lennox/clock.json","w"),indent=1)
P
check "clock: a running timer goes to Python" '$B clock waybar | grep -q "\"timer\""'
python3 - <<P
import json
json.dump({"timers":[],"alarms":[{"id":"a","time":"07:00","enabled":False,"next":None}],"reminders":[],"ringing":[],"stopwatch":{"start":None,"elapsed":0.0,"laps":[]}},open("$HOME/.local/state/lennox/clock.json","w"),indent=1)
P
check "clock: only a switched-off alarm is empty" '[ "$($B clock waybar)" = "{\"text\": \"\"}" ]'
rm -rf "$T"; exit $fail
