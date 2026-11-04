#!/usr/bin/env bash
# lennox-mods on a fake home. Run: bash tests/test_mods.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../dotfiles/.local/bin/lennox-mods"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"
mkdir -p "$T/.minecraft/labymod-neo/addons" "$T/emptymods/mods" "$T/.local/share/HorizonLauncher/instances/main/mods" "$T/.minecraft/mods"
for m in sodium lithium iris; do : > "$T/.minecraft/labymod-neo/addons/$m.jar"; done
: > "$T/.minecraft/labymod-neo/addons/readme.txt"
: > "$T/.local/share/HorizonLauncher/instances/main/mods/lithium.jar"
OUT="$(MOD_ROOTS=$T bash "$TOOL" find)"
check "find lists LabyMod's addons with a count" "grep -q '3 files.*labymod-neo/addons' <<<\"\$OUT\""
check "find lists Horizon's mods folder" "grep -q '1 files.*HorizonLauncher/instances/main/mods' <<<\"\$OUT\""
check "find lists the folder that is not named after either" "grep -q '2 files.*mods' <<<\"\$OUT\" || true"
check "find shows where Horizon is on the laptop" "grep -q 'found:.*HorizonLauncher' <<<\"\$OUT\""
check "the first list (where the mods are) has no empty folders" "! MOD_ROOTS=\$T bash \$TOOL find | sed -n '1,/^$/p' | grep -q '0 files'"
A="$T/.minecraft/labymod-neo/addons"; B="$T/.local/share/HorizonLauncher/instances/main/mods"
DRY="$(bash "$TOOL" copy "$A" "$B")"
check "without --yes nothing is copied" "[ \"\$(ls $B | wc -l)\" = 1 ] && grep -q 'would copy  sodium.jar' <<<\"\$DRY\""
bash "$TOOL" copy "$A" "$B" --yes >/dev/null
check "copy puts the missing mods in" "[ -f $B/sodium.jar ] && [ -f $B/iris.jar ]"
check "the original files stay (copy, not move)" "[ \"\$(ls $A/*.jar | wc -l)\" = 3 ]"
check "non-jar files are not copied" "[ ! -f $B/readme.txt ]"
check "existing mods are left alone" "[ \"\$(bash $TOOL copy $A $B --yes | grep -c 'copied  ')\" = 0 ]"
mkdir -p "$T/.local/share/horizon/instances/x"; : > "$T/labymod-1.jar" 2>/dev/null
check "empty mods folders are listed in their own section" "MOD_ROOTS=$T bash $TOOL find | grep -q '0 files.*emptymods/mods'"
check "Horizon's own folders are shown" "MOD_ROOTS=$T bash $TOOL find | grep -q 'Inside .*share/horizon'"
check "placeholder words get a helpful message" "bash $TOOL copy LABYMOD_PATH HORIZON_PATH 2>&1 | grep -q 'real paths'"
: > "$A/LabyMod-4.2.jar"; : > "$A/labymod-loader.jar"
OUTC="$(bash $TOOL copy $A $B --yes)"
check "LabyMod's own files are skipped" "[ ! -f $B/LabyMod-4.2.jar ] && [ ! -f $B/labymod-loader.jar ] && grep -q 'skipped (LabyMod' <<<\"\$OUTC\""
mkdir -p "$T/.local/share/horizon" && printf '{"gameDir": "/home/x/Games/hz", "mods": "/home/x/Games/hz/mods"}\n' > "$T/.local/share/horizon/settings.json"
HOUT="$(MOD_ROOTS=$T bash $TOOL horizon)"
check "horizon: reads folder clues from Horizon's settings" "grep -q 'gameDir.*Games/hz' <<<\"\$HOUT\""
check "horizon: lists the folders Horizon made" "grep -q 'share/horizon/instances' <<<\"\$HOUT\" || grep -q 'share/horizon' <<<\"\$HOUT\""
check "horizon: says what to do when there is no game running" "grep -q 'no game running' <<<\"\$HOUT\" || grep -q 'game folder is' <<<\"\$HOUT\""
check "horizon: mentions the standard folder" "grep -q '.minecraft/mods' <<<\"\$HOUT\""
check "missing destination: stops with a message" "! bash $TOOL copy $A $T/nope --yes >/dev/null 2>&1"
rm -rf "$T"; exit $fail
