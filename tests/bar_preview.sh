#!/usr/bin/env bash
R="${R:-$(cd "$SP/.." && pwd)}"
# usage: bar_preview.sh STYLE OUT.png [12h|24h] [media]
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP; B=$SP/bhome
RT=/run/lxbar
export HOME=$B XDG_RUNTIME_DIR=$RT PATH="$SP/wstubs:$B/.local/bin:$PATH"
mkdir -p $RT/lennox; chmod 700 $RT; rm -rf $RT/lennox/ws; cp -r $B/run/lennox/ws $RT/lennox/
pkill -x sway 2>/dev/null; pkill -x waybar 2>/dev/null; sleep 0.5; rm -f $RT/wayland-*
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman sway -c $SP/sway.conf > $SP/sway.log 2>&1 &
for i in $(seq 50); do ls $RT/wayland-? >/dev/null 2>&1 && break; sleep 0.1; done
export WAYLAND_DISPLAY=$(basename "$(ls $RT/wayland-? | head -1)")
export SWAYSOCK=$(ls $RT/sway-ipc.*.sock 2>/dev/null | head -1)
lennox-set bar.style "$1" --no-apply >/dev/null
lennox-set bar.clock_24h "$([ "$3" = 12h ] && echo false || echo true)" --no-apply >/dev/null
lennox-set bar.show_media "$([ "$4" = media ] && echo true || echo false)" --no-apply >/dev/null
lennox-bar start
sleep 1; pkill -x waybar; sleep 0.3
# Preview only: no Hyprland here, so use sway's window title module
jq '.["modules-left"] |= map(if . == "hyprland/window" then "sway/window" else . end)
    | .["modules-right"] |= map(select(. != "bluetooth"))
    | .["group/hardware"].modules |= map(select(. != "hyprland/language"))' $RT/lennox/waybar.json > $RT/lennox/preview.json
STYLE=$(lennox-get bar.style)
waybar -c $RT/lennox/preview.json -s $B/.config/waybar/themes/$STYLE/style.css > $RT/lennox/waybar.log 2>&1 &
sleep 3
grim -g "0,0 1600x64" "$2"
cp $RT/lennox/waybar.log $SP/waybar-$1.log 2>/dev/null
pkill -x waybar; pkill -x sway
