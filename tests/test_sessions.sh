#!/usr/bin/env bash
# lennox-sessions on a fake system. Run: bash tests/test_sessions.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../dotfiles/.local/bin/lennox-sessions"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"; mkdir -p "$T/usr/share/wayland-sessions"
printf '[Desktop Entry]\nName=Lennox (Hyprland)\nExec=/usr/local/bin/lennox-session\n' > "$T/usr/share/wayland-sessions/lennox.desktop"
printf '[Desktop Entry]\nName=Hyprland\nExec=Hyprland\n' > "$T/usr/share/wayland-sessions/hyprland.desktop"
E="env LENNOX_ROOT=$T LENNOX_SUDO="
check "status lists both sessions" "$E bash $TOOL status | grep -q 'Hyprland$' && $E bash $TOOL status | grep -q 'every session'"
$E bash "$TOOL" hide-others >/dev/null
check "hide-others writes the SDDM setting" "grep -q 'SessionDir=/usr/share/lennox/sessions' $T/etc/sddm.conf.d/20-lennox-sessions.conf"
check "the folder holds only the Lennox session" "[ \"\$(ls $T/usr/share/lennox/sessions)\" = lennox.desktop ]"
check "the Hyprland package's own files are untouched" "[ -f $T/usr/share/wayland-sessions/hyprland.desktop ]"
$E bash "$TOOL" show-all >/dev/null
check "show-all removes the setting" "[ ! -f $T/etc/sddm.conf.d/20-lennox-sessions.conf ]"
rm -f "$T/usr/share/wayland-sessions/lennox.desktop"
check "missing Lennox file: refuses" "! $E bash $TOOL hide-others >/dev/null 2>&1 && [ ! -f $T/etc/sddm.conf.d/20-lennox-sessions.conf ]"
rm -rf "$T"; exit $fail
