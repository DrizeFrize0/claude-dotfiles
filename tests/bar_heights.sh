#!/usr/bin/env bash
# Every Lennox bar style must draw at exactly its config height: the island
# reads that height to sit in the bar. Needs sway, waybar, grim, jq.
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP; R="$(cd "$SP/.." && pwd)"
B=$SP/bhome; rm -rf "$B"; mkdir -p "$B/.config" "$B/run/lennox/ws" "$B/.local/state"
rsync -a "$R/dotfiles/.config/" "$B/.config/"; rsync -a "$R/dotfiles/.local" "$B/"
bash "$SP/make_fixtures.sh"
[[ -f $SP/sway.conf ]] || echo 'output * bg #556070 solid_color resolution 1600x200' > "$SP/sway.conf"
fail=0
check() { # STYLE DENSITY TEXTURE WANT
    timeout 40 dbus-run-session bash "$SP/bar_preview.sh" "$1" "$SP/bar-$1-$2.png" 24h "" "$2" "$3" >/dev/null 2>&1
    got=$(grep -ao 'height: [0-9]*' "$SP/waybar-$1.log" | tail -1 | grep -o '[0-9]*')
    errs=$(grep -ac "Theme parsing error\|Failed to load CSS" "$SP/waybar-$1.log")
    if [[ "$got" == "$4" && "$errs" == 0 ]]; then echo "ok   $1 $2${3:+ texture} $got px"
    else echo "FAIL $1 $2 texture=$3: drawn ${got:-?} px, want $4 px, CSS errors $errs"; fail=1; fi
}
for dir in "$R"/dotfiles/.config/waybar/themes/lennox*/; do
    s=$(basename "$dir")
    check "$s" comfortable true "$(jq .height "$dir/config.json")"
    [[ -f "$dir/compact.css" ]] && check "$s" compact true "$(jq '.["x-lennox"]["compact-height"]' "$dir/config.json")"
done
exit $fail
