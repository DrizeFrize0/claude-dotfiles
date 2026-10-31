#!/usr/bin/env bash
# Every Lennox bar style must draw at exactly its config height: the island
# reads that height to sit in the bar. Needs sway, waybar, grim, jq.
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP; R="$(cd "$SP/.." && pwd)"
B=$SP/bhome; rm -rf "$B"; mkdir -p "$B/.config" "$B/run/lennox/ws" "$B/.local/state"
rsync -a "$R/dotfiles/.config/" "$B/.config/"; rsync -a "$R/dotfiles/.local" "$B/"
bash "$SP/make_fixtures.sh"
[[ -f $SP/sway.conf ]] || echo 'output * bg #556070 solid_color resolution 1600x200' > "$SP/sway.conf"
fail=0
for dir in "$R"/dotfiles/.config/waybar/themes/lennox*/; do
    s=$(basename "$dir"); want=$(jq .height "$dir/config.json")
    timeout 40 dbus-run-session bash "$SP/bar_preview.sh" "$s" "$SP/bar-$s.png" >/dev/null 2>&1
    got=$(grep -ao 'height: [0-9]*' "$SP/waybar-$s.log" | tail -1 | grep -o '[0-9]*')
    if [[ "$got" == "$want" ]]; then echo "ok   $s $got px"; else echo "FAIL $s drawn ${got:-?} px, config $want px"; fail=1; fi
done
exit $fail
