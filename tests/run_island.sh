#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
bash -c "$(sed -n '1,/^HOME=/p' $SP/run_widgets_gui.sh | sed '$d')"
H=$SP/whome
HOME=$H XDG_RUNTIME_DIR=$H/run XDG_STATE_HOME=$H/.local/state timeout -k 5 120 xvfb-run -a -s "-screen 0 1280x900x24" dbus-run-session bash $SP/island_inner.sh
