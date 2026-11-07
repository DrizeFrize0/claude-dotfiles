#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
bash -c "$(sed -n '1,/^HOME=/p' $SP/run_widgets_gui.sh | sed '$d')"   # same test home setup
H=$SP/whome
: <<"X"
  export GDK_BACKEND=x11 GSK_RENDERER=cairo NO_AT_BRIDGE=1 PATH="$SP/wstubs:$HOME/.local/bin:$PATH" MPRIS_LOG=$SP/mpris.log STUBLOG=$SP/wstub.log SP
  : > $MPRIS_LOG; : > $STUBLOG
  /usr/bin/python3.12 $SP/fake_mpris.py "$SP/cover.png" & sleep 1
  /usr/bin/python3.12 $SP/widgets_interact.py 2>&1 | grep -v "libEGL"
X

HOME=$H XDG_RUNTIME_DIR=$H/run timeout -k 5 120 xvfb-run -a -s "-screen 0 1280x900x24" dbus-run-session bash $SP/wi_big_inner.sh
