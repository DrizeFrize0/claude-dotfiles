#!/usr/bin/env bash
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
export GDK_BACKEND=x11 GSK_RENDERER=cairo NO_AT_BRIDGE=1 PATH="$SP/wstubs:$HOME/.local/bin:$PATH" MPRIS_LOG=$SP/mpris.log STUBLOG=$SP/wstub.log SP
: > $MPRIS_LOG; : > $STUBLOG
/usr/bin/python3.12 $SP/fake_mpris.py "$SP/cover.png" & sleep 1
/usr/bin/python3.12 $SP/island_interact.py 2>&1 | grep -v "libEGL"
