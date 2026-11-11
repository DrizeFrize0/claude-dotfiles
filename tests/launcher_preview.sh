#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP; H=$SP/rhome
export HOME=$H XDG_DATA_DIRS="$H/.local/share:/usr/share" XDG_DATA_HOME=$H/.local/share
display -window root $SP/wall.png & sleep 1.5
TS='window { transparency: "screenshot"; }'
case "$1" in
  apps) rofi -show drun -config $H/.config/rofi/config.rasi -theme-str 'textbox-greeting { str: "Good evening, Jado"; }' -theme-str 'textbox-date { str: "Wednesday 28 October  ·  20:47"; }' -theme-str "$TS" & ;;
  compact) printf 'Lennox Islands\nLennox Line\nML4W Modern\nML4W Glass\nML4W Minimal\n' | rofi -dmenu -i -config $H/.config/rofi/compact.rasi -p "󰕰 Bar style" -mesg "Current: lennox" -no-custom -theme-str "$TS" & ;;
  power) printf '<span font="Symbols Nerd Font 26">󰌾</span>\nLock|<span font="Symbols Nerd Font 26">󰤄</span>\nSuspend|<span font="Symbols Nerd Font 26">󰍃</span>\nLog out|<span font="Symbols Nerd Font 26">󰜉</span>\nRestart|<span font="Symbols Nerd Font 26">󰐥</span>\nShut down' | rofi -dmenu -config $H/.config/rofi/power.rasi -sep '|' -eh 2 -markup-rows -no-custom -mesg "Up 3 h 12 min" -theme-str "$TS" & ;;
  wallpaper) for n in 1 2 3 4 5 6 7; do printf 'wall-%s.jpg\0icon\x1f%s\n' $n $SP/wall-thumb.png; done | rofi -dmenu -i -config $H/.config/rofi/wallpaper.rasi -p "󰋩" -theme-str "$TS" & ;;
esac
sleep 2.5; import -window root $SP/rofi-$1.png; pkill -x rofi; pkill -x display
