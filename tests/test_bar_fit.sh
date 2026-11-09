#!/usr/bin/env bash
# lennox-bar island_fit: measures the running bar (pretend hyprctl) and writes island.json. Run: bash tests/test_bar_fit.sh
R="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
eval "$(sed -n '/^island_fit() {/,/^}/p' "$R/dotfiles/.local/bin/lennox-bar")"
RUN="$T"; WAYBAR="$R/dotfiles/.config/waybar"
mkdir -p "$T/bin"; export PATH="$T/bin:$PATH"
printf '#!/bin/sh\necho %s\n' "'{\"eDP-1\":{\"levels\":{\"2\":[{\"namespace\":\"waybar\",\"x\":10,\"y\":8,\"w\":1900,\"h\":44}]}}}'" > "$T/bin/hyprctl"; chmod +x "$T/bin/hyprctl"
echo '{"position":"top","height":40,"margin-top":8}' > "$T/waybar.json"
island_fit lennox-pills
check "measured height and margin" "[ \"\$(jq -r '.height,.top' $T/island.json | tr '\n' ' ')\" = '44 8 ' ]"
check "the style's skin" "[ \"\$(jq -r .skin $T/island.json)\" = match ]"
echo '{"position":"bottom","height":48,"margin-bottom":8}' > "$T/waybar.json"
island_fit minimal
check "bottom bar keeps its position" "[ \"\$(jq -r .position $T/island.json)\" = bottom ]"
check "minimal gets the flat skin" "[ \"\$(jq -r .skin $T/island.json)\" = flat ]"
printf '#!/bin/sh\necho "{}"\n' > "$T/bin/hyprctl"
echo '{"position":"top","margin-top":6}' > "$T/waybar.json"
island_fit glass
check "no bar measured: config values, default height" "[ \"\$(jq -r '.height,.top' $T/island.json | tr '\n' ' ')\" = '34 6 ' ]"
for t in "$WAYBAR"/themes/*/config.json; do
    jq -e '.["x-lennox"].island | IN("black","match","glass","flat","glow")' "$t" >/dev/null || { echo "FAIL no island skin: $t"; fail=1; }
done
[ "$fail" = 0 ] && echo "OK bar-fit" || echo "FAILED bar-fit"
exit "$fail"
