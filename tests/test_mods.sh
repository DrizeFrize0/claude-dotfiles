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
check "empty mods folders are not listed" "! grep -q '0 files' <<<\"\$OUT\"" 
A="$T/.minecraft/labymod-neo/addons"; B="$T/.local/share/HorizonLauncher/instances/main/mods"
DRY="$(bash "$TOOL" copy "$A" "$B")"
check "without --yes nothing is copied" "[ \"\$(ls $B | wc -l)\" = 1 ] && grep -q 'would copy  sodium.jar' <<<\"\$DRY\""
bash "$TOOL" copy "$A" "$B" --yes >/dev/null
check "copy puts the missing mods in" "[ -f $B/sodium.jar ] && [ -f $B/iris.jar ]"
check "the original files stay (copy, not move)" "[ \"\$(ls $A/*.jar | wc -l)\" = 3 ]"
check "non-jar files are not copied" "[ ! -f $B/readme.txt ]"
check "existing mods are left alone" "[ \"\$(bash $TOOL copy $A $B --yes | grep -c 'copied  ')\" = 0 ]"
check "missing destination: stops with a message" "! bash $TOOL copy $A $T/nope --yes >/dev/null 2>&1"
rm -rf "$T"; exit $fail
