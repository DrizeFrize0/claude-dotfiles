#!/usr/bin/env bash
# Full Lennox validation sweep. Usage: sweep.sh [quick]
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"; export SP
R="$(cd "$SP/.." && pwd)"
cd "$R" || exit 1
fail=0
hdr() { echo; echo "### $*"; }

hdr "shellcheck"
mapfile -t sh < <(for f in install.sh setup/system/usr/local/bin/* dotfiles/.local/bin/*; do head -1 "$f" | grep -q -E 'bash|/sh' && echo "$f"; done)
shellcheck -S warning -x "${sh[@]}" && echo "ok (${#sh[@]} scripts)" || fail=1

hdr "pyflakes + compile"
mapfile -t py < <(find dotfiles/.local/share/lennox/python -name '*.py'; for f in dotfiles/.local/bin/*; do head -1 "$f" | grep -q python && echo "$f"; done)
${PYFLAKES:-python3 -m pyflakes} "${py[@]}" && echo "ok (${#py[@]} files)" || fail=1
for f in "${py[@]}"; do /usr/bin/python3.12 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f" || fail=1; done

hdr "json"
for f in $(git ls-files -co --exclude-standard '*.json' | grep -v matugen/templates); do python3 -m json.tool "$f" >/dev/null || { echo "BAD $f"; fail=1; }; done; echo done

hdr "lua mock (variants)"
M=$SP/hl_mock.lua; W=$SP/hyprtest; RT=$SP/rt
run() { rm -rf $W $RT; cp -r dotfiles/.config/hypr $W; mkdir -p $RT/lennox/modes; printf '%s\n' "$1" > $W/lennox/settings.lua; [ -n "$2" ] && touch $RT/lennox/modes/$2
  out=$(HOME=$SP/testhome XDG_RUNTIME_DIR=$RT SCHEMA057=$SP/schema057.lua lua5.4 $M $W 2>&1); echo "$out" | grep -q '^OK' && echo "  [$3] $(echo "$out" | grep binds=)" || { echo "  [$3] FAIL"; echo "$out" | sed 's/^/     /'; fail=1; }; }
run 'LENNOX_SETTINGS = {}' "" defaults
run 'LENNOX_SETTINGS = { appearance = { animations = "off", border_style = "solid", layout = "master" } }' "" variant1
run 'LENNOX_SETTINGS = { appearance = { window_mode = "stacking" } }' "" stacking
run 'LENNOX_SETTINGS = { appearance = { animations = "bouncy", border_style = "none" }, keybinds = { main_mod = "ALT" } }' game game
run 'LENNOX_SETTINGS = "garbage"' saver broken
if [ -n "$EXTRA_LUA" ]; then while IFS='|' read -r name lua; do run "$lua" "" "$name"; done <<<"$EXTRA_LUA"; fi

[ "$1" = quick ] && { echo; [ $fail = 0 ] && echo "QUICK SWEEP PASSED" || echo "QUICK SWEEP FAILED"; exit $fail; }

hdr "daily care (prayer, heat, water)"
python3 -W error tests/test_care.py 2>&1 | tail -3 | grep -q "^OK" && echo ok || { python3 tests/test_care.py 2>&1 | tail -15; fail=1; }
python3 -W ignore tests/test_focus_subjects.py 2>&1 | tail -3 | grep -q "^OK" && echo ok focus || { python3 tests/test_focus_subjects.py 2>&1 | tail -15; fail=1; }
python3 -W ignore tests/test_extras.py 2>&1 | tail -3 | grep -q "^OK" && echo ok extras || { python3 tests/test_extras.py 2>&1 | tail -20; fail=1; }
bash tests/test_boot_animation.sh | grep -q FAIL && { bash tests/test_boot_animation.sh | grep FAIL; fail=1; } || echo ok boot animation
bash tests/overlay_smoke.sh | grep FAIL && fail=1 || echo ok overlays
python3 -W ignore tests/test_game_ping.py 2>&1 | tail -3 | grep -q "^OK" && echo ok game+ping || { python3 tests/test_game_ping.py 2>&1 | tail -15; fail=1; }
bash tests/test_sound_guard.sh | grep -q FAIL && { bash tests/test_sound_guard.sh | grep FAIL; fail=1; } || echo ok sound guard

hdr "css (gtk3/gtk4)"
C=$SP/csscheck.py; P=$R/dotfiles/.config
out=$(xvfb-run -a /usr/bin/python3.12 $C 3.0 $P/waybar/themes/*/style.css $P/nwg-dock-hyprland/style.css $P/gtk-3.0/gtk.css 2>&1; xvfb-run -a /usr/bin/python3.12 $C 4.0 $P/swaync/style.css $P/gtk-4.0/gtk.css $CSS4_EXTRA 2>&1)
out=$(echo "$out" | grep -v "libEGL\|^$"); echo "$out"; echo "$out" | grep -qv "^OK " && fail=1

hdr "bar styles"
python3 -c "
import os, sys; sys.path.insert(0,'dotfiles/.local/share/lennox/python')
from lennox import settings as S
styles = S.CHOICES[('bar', 'style')]
assert styles, 'no bar style list'
miss = [s for s in styles for f in ('config.json', 'style.css') if not os.path.exists(f'dotfiles/.config/waybar/themes/{s}/{f}')]
assert not miss, miss
print('ok', len(styles), 'styles')" || fail=1

hdr "version matches the changelog"
python3 -c "
import sys; sys.path.insert(0,'dotfiles/.local/share/lennox/python')
from lennox import whatsnew as w, VERSION
e=w.load(); k=[w.key(x['version']) for x in e]
assert e and e[0]['version']==VERSION and all(k) and k==sorted(k, reverse=True) and all(x['items'] for x in e)
print('ok', VERSION)" || fail=1

hdr "settings app (all pages)"
T=$SP/testhome; mkdir -p $T/.local/share/lennox $T/.local/bin $T/run; rsync -a --delete dotfiles/.local/share/lennox/ $T/.local/share/lennox/; mkdir -p $T/.local/bin; cp dotfiles/.local/bin/lennox-cleanup dotfiles/.local/bin/lennox-apps dotfiles/.local/bin/lennox-phone dotfiles/.local/bin/lennox-focus dotfiles/.local/bin/lennox-sound-fx dotfiles/.local/bin/lennox-bedtime dotfiles/.local/bin/lennox-backup dotfiles/.local/bin/lennox-livewall dotfiles/.local/bin/lennox-ocr dotfiles/.local/bin/lennox-panic dotfiles/.local/bin/lennox-gameprofile dotfiles/.local/bin/lennox-storage dotfiles/.local/bin/lennox-achieve dotfiles/.local/bin/lennox-autoprofile dotfiles/.local/bin/lennox-fan dotfiles/.local/bin/lennox-ping $T/.local/bin/
S=$SP/shots; rm -rf $S; mkdir -p $S
(cd $SP && HOME=$T XDG_RUNTIME_DIR=$T/run SHOTS=$S GDK_BACKEND=x11 GSK_RENDERER=cairo NO_AT_BRIDGE=1 timeout -k 5 120 xvfb-run -a -s "-screen 0 1280x800x24" dbus-run-session /usr/bin/python3.12 drive_app.py > app.log 2>&1; echo "exit $?" >> app.log)
grep -E "^ERRORS|^exit" $SP/app.log; grep -q "ERRORS: 0" $SP/app.log || { grep -v "dbus-daemon\|libEGL\|^$\|^shot" $SP/app.log | tail -30; fail=1; }

hdr "bar style gallery"
out=$(cd $SP && NO_AT_BRIDGE=1 GDK_BACKEND=x11 GSK_RENDERER=cairo timeout -k 5 60 xvfb-run -a -s "-screen 0 1280x1000x24" /usr/bin/python3.12 gallery_shot.py 2>&1 | grep -E "^(ok|FAIL)")
echo "$out"; echo "$out" | grep -q "FAILURES: 0" || fail=1

echo; [ $fail = 0 ] && echo "SWEEP PASSED" || echo "SWEEP FAILED"
exit $fail
