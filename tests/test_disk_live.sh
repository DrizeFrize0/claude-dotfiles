#!/usr/bin/env bash
# lennox-disk-live against pretend btrfs/lsblk: clean disk, declined repair, full repair, failed repair.
set -u
here="$(cd "$(dirname "$0")/.." && pwd)"
script="$here/dotfiles/.local/bin/lennox-disk-live"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"
cat >"$tmp/bin/lsblk" <<'X'
#!/usr/bin/env bash
echo "/dev/nvme0n1p6 vfat"; echo "/dev/nvme0n1p7 btrfs"
X
cat >"$tmp/bin/btrfs" <<'X'
#!/usr/bin/env bash
echo "$*" >>"$FAKE_DIR/calls"
case "$1 $2" in
  "check --readonly")
      n=$(cat "$FAKE_DIR/checks" 2>/dev/null || echo 0); echo $((n+1)) >"$FAKE_DIR/checks"
      case "$FAKE_MODE" in
        clean) echo "found 1 tree, no errors" ;;
        fixes) if [ "$n" -eq 0 ]; then echo "parent transid verify failed on 79322087424 wanted 533610 found 9322"; echo "ERROR: errors found in extent allocation tree"; else echo "no errors found"; fi ;;
        stuck) echo "parent transid verify failed on 79322087424 wanted 533610 found 9322" ;;
      esac ;;
  "check --repair") echo "repairing" ;;
  "rescue zero-log") echo "cleared" ;;
esac
exit 0
X
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH" LENNOX_LIVE_NOROOT=1 FAKE_DIR="$tmp" LENNOX_LIVE_LOG="$tmp"
fail=0
run() { rm -f "$tmp/calls" "$tmp/checks"; FAKE_MODE="$1" bash "$script" /dev/nvme0n1p7 <<<"$2" >"$tmp/out" 2>&1; echo $? >"$tmp/rc"; }
nok() { if "$@"; then echo "FAIL (should not): $*"; fail=1; fi; }
ok() { if "$@"; then :; else echo "FAIL: $*"; fail=1; fi; }

run clean ""
ok grep -q "No problems found" "$tmp/out"
ok test "$(cat "$tmp/rc")" = 0
nok grep -q -- "--repair" "$tmp/calls"

run fixes $'no\n'
ok grep -q "Nothing was changed" "$tmp/out"
nok grep -q -- "--repair" "$tmp/calls"

run fixes $'yes\nrepair\n'
ok grep -q "Nothing was changed" "$tmp/out"
nok grep -q -- "--repair" "$tmp/calls"

run fixes $'yes\nREPAIR\n'
ok grep -q "^check --repair" "$tmp/calls"
ok grep -q "^rescue zero-log" "$tmp/calls"
ok grep -q "Repaired" "$tmp/out"
ok test "$(cat "$tmp/rc")" = 0

run stuck $'yes\nREPAIR\n'
ok grep -q "btrfs restore" "$tmp/out"
ok test "$(cat "$tmp/rc")" = 2

# with no argument it finds the btrfs partition itself
rm -f "$tmp/calls" "$tmp/checks"; FAKE_MODE=clean bash "$script" </dev/null >"$tmp/out" 2>&1
ok grep -q "Disk to check: /dev/nvme0n1p7" "$tmp/out"

[ "$fail" = 0 ] && echo "OK disk-live" || echo "FAILED disk-live"
exit "$fail"
