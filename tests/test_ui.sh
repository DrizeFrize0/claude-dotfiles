#!/usr/bin/env bash
# The terminal look: plain without a terminal, colored with one, boxes line up, durations read well.
# Run: bash tests/test_ui.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI="$SP/../setup/lib/ui.sh"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
run() { bash -c "WARNINGS=(); source '$UI'; $1" 2>&1; }

# 1. no terminal, no colors
OUT="$(run 'ui_init; ui_banner "upgrade" "1.30.2 -> 1.33.0"; step "One"; ok "fine"; warn "careful"; ui_done "Lennox is up to date"')"
check "no escape codes in a pipe" "! grep -q $'\\e' <<<\"\$OUT\""
check "the banner shows the name, the title and the versions" "grep -q 'LENNOX   upgrade' <<<\"\$OUT\" && grep -q '1.30.2 -> 1.33.0' <<<\"\$OUT\""
check "steps, checks and warnings are marked" "grep -q '◆ One' <<<\"\$OUT\" && grep -q '✓ fine' <<<\"\$OUT\" && grep -q '▲ careful' <<<\"\$OUT\""
check "the end box and the warnings list" "grep -q 'OK  Lennox is up to date' <<<\"\$OUT\" && grep -q 'A few things to look at' <<<\"\$OUT\""

# 2. the boxes line up: every box line has the same width
WIDTHS="$(grep -E '^  (│|╭|╰)' <<<"$OUT" | python3 -c 'import sys; print(len({len(l.rstrip("\n")) for l in sys.stdin}))')"
check "all box lines are the same width" "[ \"$WIDTHS\" = 1 ]"

# 3. colors only when asked for, and removable for the log
COL="$(run 'LENNOX_COLOR=1; ui_init; step "Colored"; ok "x"')"
check "colors appear with LENNOX_COLOR" "grep -q $'\\e' <<<\"\$COL\""
check "ui_strip removes them" "[ \"\$(printf '%s\\n' \"\$COL\" | bash -c \"source $UI; ui_strip\" | grep -c $'\\e')\" = 0 ]"
NC="$(NO_COLOR=1 LENNOX_COLOR= run 'ui_init; ok x')"
check "NO_COLOR is respected" "! grep -q $'\\e' <<<\"\$NC\""

# 4. durations
D="$(run 'ui_init; ui_duration 5; echo; ui_duration 72; echo; ui_duration 3725')"
check "durations: 5s, 1m 12s, 1h 02m" "grep -qx '5s' <<<\"\$D\" && grep -qx '1m 12s' <<<\"\$D\" && grep -qx '1h 02m' <<<\"\$D\""

# 5. a slow step reports how long it took, a quick one does not
SLOW="$(bash -c "WARNINGS=(); source $UI; ui_init; step A; SECONDS=\$((SECONDS+7)); step B; ui_close_step" 2>&1)"
check "a slow step says how long it took" "grep -q 'took 7s' <<<\"\$SLOW\""
check "a quick step stays quiet" "! run 'ui_init; step A; step B' | grep -q took"

# 6. dying prints the log hint and exits non-zero
check "die exits with an error and names the log" "! bash -c \"WARNINGS=(); source $UI; ui_init; LOGFILE=/tmp/x.log; die 'broke'\" >/tmp/ui-die.out 2>&1 && grep -q 'Full log: /tmp/x.log' /tmp/ui-die.out"
rm -f /tmp/ui-die.out
exit $fail
