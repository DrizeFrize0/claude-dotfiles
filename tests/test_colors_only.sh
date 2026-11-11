#!/usr/bin/env bash
# lennox-wallpaper with LENNOX_COLORS_ONLY: the colors come from the picture, but the wallpaper, the lock screen
# pictures and the "current wallpaper" note stay as they were. Run: bash tests/test_colors_only.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$SP/.." && pwd)"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"
mkdir -p "$T/home" "$T/stubs" "$T/run"
cp -r "$R/dotfiles/.local" "$T/home/"
convert -size 64x64 xc:'#3366cc' "$T/wall.png"; convert -size 64x64 xc:'#cc3366' "$T/cover.png"
for c in matugen hyprctl swaync-client; do printf '#!/bin/sh\necho "%s $@" >> %s/calls\n' "$c" "$T" > "$T/stubs/$c"; chmod +x "$T/stubs/$c"; done
export HOME="$T/home" XDG_RUNTIME_DIR="$T/run" PATH="$T/stubs:$T/home/.local/bin:$PATH" XDG_CONFIG_HOME="$T/home/.config" XDG_CACHE_HOME="$T/home/.cache"
unset WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE
CUR="$T/home/.cache/lennox/wallpaper/current"
bash "$T/home/.local/bin/lennox-wallpaper" "$T/wall.png" --theme-only --quiet >/dev/null 2>&1
HAVE_MAGICK=false; command -v magick >/dev/null && HAVE_MAGICK=true       # the lock screen pictures need ImageMagick 7
check "a normal run notes the wallpaper" "grep -q wall.png $CUR"
$HAVE_MAGICK && check "a normal run makes the lock screen picture" "[ -f $T/home/.cache/lennox/wallpaper/blurred.png ]"
rm -f "$T/home/.cache/lennox/wallpaper/blurred.png"; : > "$T/calls"
LENNOX_COLORS_ONLY=1 bash "$T/home/.local/bin/lennox-wallpaper" "$T/cover.png" --theme-only --quiet >/dev/null 2>&1
check "colors-only: matugen was asked for the cover's colors" "grep -q 'matugen image .*cover.png' $T/calls"
check "colors-only: the current-wallpaper note is untouched" "grep -q wall.png $CUR && ! grep -q cover.png $CUR"
check "colors-only: no new lock screen picture" "[ ! -f $T/home/.cache/lennox/wallpaper/blurred.png ]"
bash "$T/home/.local/bin/lennox-wallpaper" --restore --theme-only --quiet >/dev/null 2>&1
check "restore: back to the wallpaper's colors" "grep -q 'matugen image .*wall.png' $T/calls"
$HAVE_MAGICK && check "restore: and its lock screen picture" "[ -f $T/home/.cache/lennox/wallpaper/blurred.png ]"
rm -rf "$T"; exit $fail
