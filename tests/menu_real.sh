#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP; H=$SP/rhome
export HOME=$H XDG_DATA_DIRS="$H/.local/share:/usr/share" PATH="$H/.local/bin:$PATH"
display -window root $SP/wall.png & sleep 1.5
# Preview only: no compositor here, so rofi fakes its transparency
mkdir -p $SP/rofiwrap; printf '#!/bin/sh\nexec /usr/bin/rofi "$@" -theme-str "window { transparency: \\"screenshot\\"; }"\n' > $SP/rofiwrap/rofi; chmod +x $SP/rofiwrap/rofi
PATH="$SP/rofiwrap:$PATH" lennox-menu "$1" & sleep 3
import -window root $SP/real-$1.png; pkill -x rofi; pkill -x display
