#!/usr/bin/env bash
# Test fixtures that aren't kept in git (tests/ ignores everything but scripts):
# fake album covers and stubs for the system commands the widgets call.
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
IM=convert; command -v magick >/dev/null && IM=magick
[[ -f $SP/cover.png ]] || $IM -size 600x600 gradient:'#ff2d55-#5856d6' "$SP/cover.png"
[[ -f $SP/bigcover.png ]] || $IM -size 3000x3000 gradient:'#30d158-#0a84ff' "$SP/bigcover.png"
S=$SP/wstubs; mkdir -p "$S"
stub() { printf '#!/usr/bin/env bash\necho "$*" >> "${STUBLOG:-/dev/null}"\n%s\n' "$2" > "$S/$1"; chmod +x "$S/$1"; }
stub wpctl 'case "$1" in get-volume) echo "Volume: 0.45" ;; esac'
stub brightnessctl 'for a; do [[ $a == -m ]] && echo "intel_backlight,backlight,50,50%,100"; done; true'
