#!/usr/bin/env bash
# Every overlay window opens, draws for a few seconds and raises no errors (headless X11, no layer shell).
# Run: bash tests/overlay_smoke.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$SP/.." && pwd)"
T="$(mktemp -d)"
mkdir -p "$T/home" "$T/run" "$T/bin"
cp -r "$R/dotfiles/.local" "$T/home/"
cat > "$T/bin/cava" <<'CAVA'
#!/bin/sh
i=0
while [ $i -lt 400 ]; do echo "12;55;90;30;70;20;44;66;80;15;33;99"; i=$((i+1)); sleep 0.05; done
CAVA
chmod +x "$T/bin/cava"
fail=0
run() {  # run NAME SECONDS MODULE ARGS...
    local name="$1" secs="$2"; shift 2
    local out
    out="$(HOME="$T/home" XDG_RUNTIME_DIR="$T/run" GDK_BACKEND=x11 GSK_RENDERER=cairo NO_AT_BRIDGE=1 LENNOX_WIDGETS_NO_LAYER=1 \
        PYTHONPATH="$T/home/.local/share/lennox/python" PATH="$T/bin:$PATH" \
        timeout "$secs" xvfb-run -a -s "-screen 0 1280x800x24" /usr/bin/python3.12 -m "$@" 2>&1 | grep -v "libEGL\|^$")"
    if grep -q "Traceback\|Error\|CRITICAL" <<<"$out"; then echo "FAIL $name"; echo "$out" | head -8; fail=1; else echo "ok   $name"; fi
}
run "screensaver stars"  15 lennox.screensaver stars --seconds 2
run "screensaver rain"   15 lennox.screensaver rain --seconds 2
run "screensaver aurora" 15 lennox.screensaver aurora --seconds 2
run "music wallpaper"     4 lennox.visualizer run
run "cursor effects"      4 lennox.cursorfx run
run "desktop pet"         4 lennox.pet run
run "snake"               4 lennox.minigames snake
run "flappy"              4 lennox.minigames flappy
run "ask window"          4 lennox.ask
rm -rf "$T"
exit $fail
