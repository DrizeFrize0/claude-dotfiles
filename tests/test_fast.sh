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

# ---- system monitor: the Rust output must equal the Python output, character for character
mk() {  # mk DIR: a made-up /sys and /proc (the numbers change half way through the half second)
    rm -rf "$1"; mkdir -p "$1/sys/class/hwmon/hwmon0" "$1/sys/class/hwmon/hwmon1" "$1/sys/class/hwmon/hwmon2" "$1/sys/class/power_supply/BAT0" \
        "$1/sys/bus/pci/devices/0000:01:00.0/power" "$1/proc/101" "$1/proc/202" "$1/proc/303"
    echo coretemp > "$1/sys/class/hwmon/hwmon0/name"; echo 79500 > "$1/sys/class/hwmon/hwmon0/temp1_input"
    echo hp > "$1/sys/class/hwmon/hwmon1/name"; echo 2200 > "$1/sys/class/hwmon/hwmon1/fan1_input"; echo 0 > "$1/sys/class/hwmon/hwmon1/fan2_input"
    echo nvme > "$1/sys/class/hwmon/hwmon2/name"; echo 41000 > "$1/sys/class/hwmon/hwmon2/temp1_input"
    echo Discharging > "$1/sys/class/power_supply/BAT0/status"; echo 11250000 > "$1/sys/class/power_supply/BAT0/power_now"
    echo 0x10de > "$1/sys/bus/pci/devices/0000:01:00.0/vendor"; echo 0x030200 > "$1/sys/bus/pci/devices/0000:01:00.0/class"
    echo suspended > "$1/sys/bus/pci/devices/0000:01:00.0/power/runtime_status"
    printf 'MemTotal: 16000000 kB\nMemFree: 1000 kB\nMemAvailable: 6000000 kB\n' > "$1/proc/meminfo"
    echo "cpu 1000 0 500 8000 100 0 0 0 0 0" > "$1/proc/stat"
    echo "101 (firefox) S 1 1 1 0 0 0 0 0 0 0 100 50 0 0 0 0 0 0 0 0" > "$1/proc/101/stat"
    echo "202 (Web Content) S 1 1 1 0 0 0 0 0 0 0 10 5 0 0 0 0 0 0 0 0" > "$1/proc/202/stat"
    echo "303 (idle thing) S 1 1 1 0 0 0 0 0 0 0 1 1 0 0 0 0 0 0 0 0" > "$1/proc/303/stat"
    ( sleep 0.25; echo "cpu 1300 0 600 8200 100 0 0 0 0 0" > "$1/proc/stat"
      echo "101 (firefox) S 1 1 1 0 0 0 0 0 0 0 130 70 0 0 0 0 0 0 0 0" > "$1/proc/101/stat"
      echo "202 (Web Content) S 1 1 1 0 0 0 0 0 0 0 12 8 0 0 0 0 0 0 0 0" > "$1/proc/202/stat" ) &
}
M="$T/mon"
mk "$M"; RUST_OUT="$(LENNOX_SYS=$M/sys LENNOX_PROC=$M/proc $B sysmon waybar)"; wait
mk "$M"; PY_OUT="$(cd "$SP/../dotfiles/.local/share/lennox/python" && LENNOX_SYS=$M/sys LENNOX_PROC=$M/proc python3 -m lennox.sysmon waybar)"; wait
check "sysmon: Rust prints exactly what Python prints" '[ "$RUST_OUT" = "$PY_OUT" ] && [ -n "$RUST_OUT" ]'
[ "$RUST_OUT" = "$PY_OUT" ] || { echo "rust: $RUST_OUT"; echo "py:   $PY_OUT"; }
echo awake > "$M/sys/bus/pci/devices/0000:01:00.0/power/runtime_status"
check "sysmon: an awake NVIDIA chip goes to Python" 'LENNOX_SYS=$M/sys LENNOX_PROC=$M/proc $B sysmon waybar | grep -q "\"class\""'

# ---- settings: lennox-get
mkdir -p "$HOME/.config/lennox"; echo '{"bar": {"style": "glass", "x": true, "n": 7}}' > "$HOME/.config/lennox/settings.json"
check "get: text" '[ "$($B get bar.style)" = glass ]'
check "get: true/false" '[ "$($B get bar.x)" = true ]'
check "get: number" '[ "$($B get bar.n)" = 7 ]'
check "get: a missing key falls back to the default from Python" '[ -n "$($B get appearance.rounding)" ]'
check "get: an unknown setting is an error" '! $B get nope.nothing 2>/dev/null'
rm -rf "$T"; exit $fail
