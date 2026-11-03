#!/usr/bin/env bash
# lennox-bootmenu on a fake boot partition: refuses when unsafe, changes only what it says, undoes cleanly.
# Run: bash tests/test_bootmenu.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../dotfiles/.local/bin/lennox-bootmenu"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }

mk() {   # mk DIR : a fake system with an ESP holding an Arch UKI and stubs
    local T="$1"
    mkdir -p "$T/esp/EFI/Linux" "$T/esp/EFI/Microsoft/Boot" "$T/esp/EFI/BOOT" "$T/bin" "$T/state"
    : > "$T/esp/EFI/Linux/archlinux.efi"; : > "$T/esp/EFI/Microsoft/Boot/bootmgfw.efi"; : > "$T/esp/EFI/BOOT/BOOTX64.EFI"
    printf '#!/bin/sh\nif [ "$1" = "-B" ]; then echo "efibootmgr $*" >> %s/calls; exit 0; fi\nif [ "$1" = "-o" ]; then echo "efibootmgr $*" >> %s/calls; exit 0; fi\ncat %s/entries 2>/dev/null\n' "$T" "$T" "$T" > "$T/bin/efibootmgr"
    printf 'BootCurrent: 0003\nBootOrder: 0000,0003\nBoot0000* Windows Boot Manager\nBoot0003* Arch Linux UKI\n' > "$T/entries"
    printf '#!/bin/sh\necho "refind-install $*" >> %s/calls\n' "$T" > "$T/bin/refind-install"
    printf '#!/bin/sh\necho "pacman $*" >> %s/calls\n' "$T" > "$T/bin/pacman"
    chmod +x "$T/bin"/*
}
env_for() { echo "env PATH=$1/bin:$PATH LENNOX_ESP=$1/esp LENNOX_SUDO= LENNOX_STATE=$1/state LENNOX_SB_FILE=$1/nosb"; }

T="$(mktemp -d)"; mk "$T"; E="$(env_for "$T")"
check "refuses without --yes" "! $E bash $TOOL enable >/dev/null 2>&1"
check "plan changes nothing" "$E bash $TOOL plan >/dev/null; [ ! -d $T/esp/EFI/refind ]"
check "status finds the Arch file" "$E bash $TOOL status | grep -q 'EFI/Linux/archlinux.efi'"

# Secure Boot on -> blocked, nothing changed
printf '\x07\x00\x00\x00\x01' > "$T/sb"
check "Secure Boot on: stops and changes nothing" "! env PATH=$T/bin:$PATH LENNOX_ESP=$T/esp LENNOX_SUDO= LENNOX_STATE=$T/state LENNOX_SB_FILE=$T/sb bash $TOOL enable --yes >/dev/null 2>&1 && [ ! -d $T/esp/EFI/refind ] && [ ! -f $T/calls ]"

: > "$T/calls"
$E bash "$TOOL" enable --yes >/dev/null 2>&1
check "backup of boot entries saved" "ls $T/state/efi-backup-*.txt >/dev/null 2>&1 && grep -q 'BootOrder: 0000,0003' $T/state/efi-backup-*.txt"
check "refind already installed: pacman not asked" "! grep -q pacman $T/calls"
check "lennox.conf has the Arch entry" "grep -q 'loader /EFI/Linux/archlinux.efi' $T/esp/EFI/refind/lennox.conf"
check "default is Arch, 8 second timeout" "grep -q 'default_selection \"Arch Linux\"' $T/esp/EFI/refind/lennox.conf && grep -q 'timeout 8' $T/esp/EFI/refind/lennox.conf"
check "included once in refind.conf" "[ \"\$(grep -c 'include lennox.conf' $T/esp/EFI/refind/refind.conf)\" = 1 ]"
$E bash "$TOOL" enable --yes >/dev/null 2>&1
check "second run doesn't duplicate the include" "[ \"\$(grep -c 'include lennox.conf' $T/esp/EFI/refind/refind.conf)\" = 1 ]"
check "Windows files untouched" "[ -f $T/esp/EFI/Microsoft/Boot/bootmgfw.efi ] && [ -f $T/esp/EFI/BOOT/BOOTX64.EFI ]"

printf 'BootOrder: 0001,0000,0003\nBoot0001* rEFInd Boot Manager\nBoot0000* Windows Boot Manager\nBoot0003* Arch Linux UKI\n' > "$T/entries"
: > "$T/calls"
$E bash "$TOOL" disable --yes >/dev/null 2>&1
check "disable removes rEFInd files" "[ ! -d $T/esp/EFI/refind ]"
check "disable removes only the rEFInd entry" "grep -q 'efibootmgr -B -b 0001' $T/calls && ! grep -q 'efibootmgr -B -b 0000\|-b 0003' $T/calls"
check "disable restores the old order" "grep -q 'efibootmgr -o 0000,0003' $T/calls"
check "Windows still there after disable" "[ -f $T/esp/EFI/Microsoft/Boot/bootmgfw.efi ]"
rm -rf "$T"

# refind missing: it is installed first
T="$(mktemp -d)"; mk "$T"; rm -f "$T/bin/refind-install"
$(env_for "$T") bash "$TOOL" enable --yes >/dev/null 2>&1
check "refind missing: pacman installs it" "grep -q 'pacman -S --needed --noconfirm refind' $T/calls"
rm -rf "$T"

# The Arch file sits at the top of the partition, not under EFI/Linux
T="$(mktemp -d)"; mk "$T"; mv "$T/esp/EFI/Linux/archlinux.efi" "$T/esp/archlinux.efi"
check "finds archlinux.efi at the top of the partition" "$(env_for "$T") bash $TOOL status | grep -q '  /archlinux.efi'"
$(env_for "$T") bash "$TOOL" enable --yes >/dev/null 2>&1
check "uses it as the Arch entry" "grep -q 'loader /archlinux.efi' $T/esp/EFI/refind/lennox.conf"
rm -rf "$T"

# Like the real laptop: the file is arch-linux.efi, and GRUB files are on the partition too
T="$(mktemp -d)"; mk "$T"; mv "$T/esp/EFI/Linux/archlinux.efi" "$T/esp/EFI/Linux/arch-linux.efi"; mkdir -p "$T/esp/grub/x86_64-efi"; : > "$T/esp/grub/x86_64-efi/core.efi"; : > "$T/esp/grub/x86_64-efi/grub.efi"
check "picks arch-linux.efi, ignores GRUB's own files" "[ \"\$($(env_for "$T") bash $TOOL status | grep -c 'efi$')\" = 1 ] || $(env_for "$T") bash $TOOL status | grep -q '/EFI/Linux/arch-linux.efi'"
$(env_for "$T") bash "$TOOL" enable --yes >/dev/null 2>&1
check "Arch entry points at arch-linux.efi" "grep -q 'loader /EFI/Linux/arch-linux.efi' $T/esp/EFI/refind/lennox.conf && grep -q 'dont_scan_files arch-linux.efi' $T/esp/EFI/refind/lennox.conf"
rm -rf "$T"

# No UKI on the partition: stops
T="$(mktemp -d)"; mk "$T"; rm -f "$T/esp/EFI/Linux/archlinux.efi"
check "no Linux file: stops" "! $(env_for "$T") bash $TOOL enable --yes >/dev/null 2>&1 && [ ! -d $T/esp/EFI/refind ]"
check "no Linux file: says what IS there" "$(env_for "$T") bash $TOOL enable --yes 2>&1 | grep -q 'bootmgfw.efi'"
rm -rf "$T"
exit $fail
