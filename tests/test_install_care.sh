#!/usr/bin/env bash
# install.sh setup_care / setup_memtest with sudo, pacman and systemctl stubbed. Run: bash tests/test_install_care.sh
R="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
# Pull just the two functions out of the installer
eval "$(sed -n '/^setup_care() {/,/^}/p; /^setup_memtest() {/,/^}/p' "$R/install.sh")"
LOG="$T/log"; SETUP="$R/setup"
step() { echo "step $*" >>"$LOG"; }; ok() { echo "ok $*" >>"$LOG"; }; warn() { echo "warn $*" >>"$LOG"; }; note() { echo "note $*" >>"$LOG"; }
pacman_install() { echo "pacman $*" >>"$LOG"; }
install_system_file() { [[ -f "$SETUP/system/$1" ]] && echo "file $1" >>"$LOG" || echo "MISSING $1" >>"$LOG"; }
sudo() { echo "sudo $*" >>"$LOG"; [[ "$1" == tee ]] && cat >"$T/tee.$(basename "$2")"; return 0; }
findmnt() { echo "${FAKE_FS:-btrfs}"; }

mkdir -p "$T/boot/memtest86+"; touch "$T/boot/memtest86+/memtest86x64.efi"; export LENNOX_BOOT="$T/boot"
BOOTLOADER=systemd-boot FAKE_FS=btrfs setup_care
check "installs the care packages" "grep -q 'pacman zram-generator earlyoom pacman-contrib memtest86+-efi' $LOG"
check "every system file exists in the repo" "! grep -q MISSING $LOG && [ \$(grep -c '^file ' $LOG) -ge 5 ]"
check "earlyoom, paccache and trim are enabled" "grep -q 'enable --now earlyoom.service' $LOG && grep -q 'enable --now paccache.timer' $LOG"
check "btrfs gets the monthly scrub" "grep -q 'btrfs-scrub@-.timer' $LOG"
check "systemd-boot gets a memtest entry" "grep -q 'efi     /memtest86+/memtest86x64.efi' $T/tee.lennox-memtest.conf"
: >"$LOG"; rm -f "$T"/tee.*
BOOTLOADER=grub FAKE_FS=ext4 setup_care
check "ext4: no scrub" "! grep -q btrfs-scrub $LOG"
check "grub: menu rebuilt, no hand-made entry" "grep -q 'grub-mkconfig' $LOG && ! ls $T/tee.* >/dev/null 2>&1"
: >"$LOG"; rm -f "$T/boot/memtest86+/memtest86x64.efi"
BOOTLOADER=systemd-boot setup_memtest
check "no memtest file: says so, writes nothing" "grep -q 'note memtest86+ is not in /boot' $LOG && ! grep -q tee $LOG"
# earlyoom's line must survive systemd's split-on-spaces (no quotes, no spaces inside a pattern)
args="$(sed -n 's/^EARLYOOM_ARGS=//p' "$R/setup/system/etc/default/earlyoom")"
check "earlyoom arguments have no quotes" "! grep -q \"[\\\"']\" <<<\"\$args\""
check "earlyoom arguments split into 10 words" "[ \$(wc -w <<<\"\$args\") -eq 10 ]"
check "zram config is marked as Lennox's" "grep -q Lennox $R/setup/system/etc/systemd/zram-generator.conf"
[ "$fail" = 0 ] && echo "OK install-care" || echo "FAILED install-care"
exit "$fail"
