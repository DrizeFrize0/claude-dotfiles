#!/usr/bin/env bash
# Run inside: dbus-run-session xvfb-run ... (see run_widgets_gui.sh)
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
OUT=$SP/wshots; mkdir -p $OUT
export LENNOX_WIDGETS_NO_LAYER=1 GDK_BACKEND=x11 GSK_RENDERER=cairo NO_AT_BRIDGE=1
export PATH="$SP/wstubs:$HOME/.local/bin:$PATH" MPRIS_LOG=$SP/mpris.log STUBLOG=$SP/wstub.log
: > $MPRIS_LOG; : > $STUBLOG
shot() { sleep "${2:-2}"; import -window root "$OUT/$1.png"; echo "shot $1"; }

/usr/bin/python3.12 $SP/fake_mpris.py "$SP/cover.png" &
sleep 1
python3() { /usr/bin/python3.12 "$@"; }; export -f python3
lennox-widgets > $SP/widgets.log 2>&1 &
WPID=$!
shot 1-desktop 4

lennox-widgets dashboard open; echo "dashboard open exit=$?"
shot 2-dashboard 3

# Second instance forwarding + bad command
lennox-widgets bogus; echo "bogus exit=$? (want 2)"
lennox-widgets dashboard toggle; echo "toggle exit=$?"
shot 3-closed 1
lennox-widgets dashboard toggle
sleep 1

# Change settings live: move widgets, 12h clock, hide system; colors change
python3 - <<'EOF'
import json, os
p = os.path.expanduser("~/.config/lennox/settings.json")
d = json.load(open(p)); d["widgets"]["position"] = "top-right"; d["widgets"]["show_system"] = False
d["bar"]["clock_24h"] = False
json.dump(d, open(p, "w"))
c = os.path.expanduser("~/.config/lennox/colors.json")
d = json.load(open(c)); d["primary"] = "#ffb4d0"; d["surface"] = "#1a1015"; json.dump(d, open(c, "w"))
EOF
shot 4-live-reload 3
lennox-widgets reload; echo "reload exit=$?"

lennox-widgets quit; echo "quit exit=$?"
sleep 1
kill -0 $WPID 2>/dev/null && echo "STILL RUNNING (bad)" || echo "daemon exited"
lennox-widgets quit; echo "quit when not running exit=$? (should not hang)"
echo "--- mpris calls:"; cat $MPRIS_LOG
echo "--- stub calls:"; cat $STUBLOG
echo "--- widgets log:"; cat $SP/widgets.log
kill %1 2>/dev/null
