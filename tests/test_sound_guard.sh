#!/usr/bin/env bash
# lennox-sound: Bluetooth config, mic-awake config and the guard, against a fake pactl.
# Run: bash tests/test_sound_guard.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../dotfiles/.local/bin/lennox-sound"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }

T="$(mktemp -d)"; mkdir -p "$T/bin" "$T/cfg" "$T/run"
# A fake sound server: state in files, every call logged
cat > "$T/bin/pactl" <<'PACTL'
#!/bin/bash
echo "pactl $*" >> "$FAKE/calls"
case "$*" in
    "-f json list cards") cat "$FAKE/cards.json" ;;
    "get-default-source") cat "$FAKE/default-source" 2>/dev/null ;;
    "list short sources") cat "$FAKE/sources" ;;
    "info") exit 0 ;;
    *) exit 0 ;;
esac
PACTL
chmod +x "$T/bin/pactl"
export FAKE="$T" PATH="$T/bin:$PATH" XDG_CONFIG_HOME="$T/cfg" XDG_RUNTIME_DIR="$T/run" HOME="$T"
run() { bash "$TOOL" "$@" 2>&1; }

# 1. configs
run bluetooth hifi >/dev/null
BT="$T/cfg/wireplumber/wireplumber.conf.d/61-lennox-bluetooth.conf"
check "hifi: no call-mode roles (a2dp only)" "grep -q 'bluez5.roles = \[ a2dp_sink a2dp_source \]' $BT"
check "hifi: no autoswitch" "grep -q 'autoswitch-to-headset-profile = false' $BT"
check "hifi: SBC-XQ on" "grep -q 'bluez5.enable-sbc-xq = true' $BT"
check "mic never sleeps" "grep -q 'session.suspend-timeout-seconds = 0' $T/cfg/wireplumber/wireplumber.conf.d/64-lennox-mic-awake.conf"
run bluetooth headset-mic >/dev/null
check "headset-mic mode removes the roles file" "[ ! -f $BT ]"
run bluetooth hifi >/dev/null

# 2. headphones in call mode -> music mode
cat > "$T/cards.json" <<'JSON'
[{"name":"bluez_card.AA_BB","active_profile":"headset-head-unit-msbc","profiles":{
  "a2dp-sink-sbc":{"priority":16,"available":true},"a2dp-sink-sbc_xq":{"priority":18,"available":true},
  "headset-head-unit":{"priority":30,"available":true}}}]
JSON
echo "alsa_input.pci.analog-stereo" > "$T/default-source"
printf '1\talsa_input.pci.analog-stereo\tm\ts16\n' > "$T/sources"
: > "$T/calls"
run guard once >/dev/null
check "call mode -> best A2DP (sbc_xq)" "grep -q 'set-card-profile bluez_card.AA_BB a2dp-sink-sbc_xq' $T/calls"
check "no mute change when not logging in" "! grep -q set-source-mute $T/calls"

# 3. login unmutes the mic
: > "$T/calls"; run guard once login >/dev/null
check "login: mic unmuted" "grep -q 'set-source-mute @DEFAULT_SOURCE@ 0' $T/calls"

# 4. default mic is a speaker's loopback -> a real mic
echo "alsa_output.pci.analog-stereo.monitor" > "$T/default-source"
printf '0\talsa_output.pci.analog-stereo.monitor\tm\n1\talsa_input.pci.analog-stereo\tm\n' > "$T/sources"
: > "$T/calls"; run guard once >/dev/null
check "monitor as default mic -> real mic" "grep -q 'set-default-source alsa_input.pci.analog-stereo' $T/calls"

# 5. clean mic on: it becomes the default mic instead
touch "$T/cfg/pipewire/pipewire.conf.d/60-lennox-clean-mic.conf" 2>/dev/null || { mkdir -p "$T/cfg/pipewire/pipewire.conf.d"; touch "$T/cfg/pipewire/pipewire.conf.d/60-lennox-clean-mic.conf"; }
printf '0\talsa_output.pci.analog-stereo.monitor\tm\n1\tlennox_clean_mic\tm\n' > "$T/sources"
: > "$T/calls"; run guard once >/dev/null
check "clean mic exists: it becomes the default" "grep -q 'set-default-source lennox_clean_mic' $T/calls"

# 6. a healthy setup is left alone (headphones already in music mode)
sed -i 's/"active_profile":"headset-head-unit-msbc"/"active_profile":"a2dp-sink-sbc_xq"/' "$T/cards.json"
echo "lennox_clean_mic" > "$T/default-source"
: > "$T/calls"; run guard once >/dev/null
check "healthy: nothing changed" "! grep -q 'set-default-source\|set-card-profile' $T/calls"

rm -rf "$T"
exit $fail
