#!/usr/bin/env bash
# The root helper behind the fan profiles writes only the two power limits. Run: bash tests/test_cpucap.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../setup/system/usr/local/bin/lennox-cpucap"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"; echo 0 > "$T/no_turbo"; echo 100 > "$T/max_perf_pct"
run() { LENNOX_PSTATE_DIR="$T" bash "$TOOL" "$1"; }
run silent; check "silent: turbo off, 60%" "[ \"\$(cat $T/no_turbo)\" = 1 ] && [ \"\$(cat $T/max_perf_pct)\" = 60 ]"
run cool;   check "cool: turbo on, 80%" "[ \"\$(cat $T/no_turbo)\" = 0 ] && [ \"\$(cat $T/max_perf_pct)\" = 80 ]"
run turbo;  check "turbo: turbo on, 100%" "[ \"\$(cat $T/no_turbo)\" = 0 ] && [ \"\$(cat $T/max_perf_pct)\" = 100 ]"
run normal; check "normal: turbo on, 100%" "[ \"\$(cat $T/max_perf_pct)\" = 100 ]"
check "anything else is refused and changes nothing" "! LENNOX_PSTATE_DIR=$T bash $TOOL rm-rf 2>/dev/null && [ \"\$(cat $T/max_perf_pct)\" = 100 ]"
rm -rf "$T"; exit $fail
