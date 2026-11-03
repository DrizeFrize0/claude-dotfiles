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
# clean: only entries whose partition is gone (your real list, with only the current partitions present)
T="$(mktemp -d)"; mk "$T"; mkdir -p "$T/partuuid"
for g in 0242629d-8edd-4521-95df-fae734237d94 8c5418f7-2b28-4dc0-8edd-1da1654ebe81 ca424f1b-844a-409f-aafc-3d7c46515bf3 aaaaaaaa-0000-0000-0000-000000000001; do : > "$T/partuuid/$g"; done
cat > "$T/entries" <<'LIST'
BootOrder: 0012,0011,9999,0010,000F,000E,000D,001C
Boot0000  Linux Boot Manager	HD(1,GPT,64df6d0e-a5d8-4b9b-9c1b-15d92b06a326,0x800,0x200000)/\EFI\systemd\systemd-bootx64.efi
Boot0002  debian	HD(1,GPT,4fd4414a-60bb-426b-8b20-0d41bb42f31e,0x800,0x100000)/\EFI\debian\grubx64.efi
Boot000D* kali	HD(1,GPT,ad6d3b8a-c588-49a4-b2ec-5666d9d79e89,0x800,0x1e8000)/\EFI\kali\grubx64.efi
Boot000F* Windows Boot Manager	HD(1,GPT,0242629d-8edd-4521-95df-fae734237d94,0x800,0x64000)/\EFI\Microsoft\Boot\bootmgfw.efi
Boot0011* Arch	HD(5,GPT,d33875da-6fde-4935-88db-982e66092315,0x3b836000,0x1aa800)/\EFI\systemd\systemd-bootx64.efi
Boot0012* rEFInd Boot Manager	HD(6,GPT,ca424f1b-844a-409f-aafc-3d7c46515bf3,0x2a651800,0x200000)/\EFI\refind\refind_x64.efi
Boot001C* Solid State Disk	PciRoot(0x0)/Pci(0x6,0x0)/NVMe(0x1,00-A0)/HD(1,GPT,0242629d-8edd-4521-95df-fae734237d94,0x800,0x64000)0000424f
Boot9999* USB Drive (UEFI)	PciRoot(0x0)/Pci(0x1d,0x0)/USB(16,0)0000424f
LIST
EC="env PATH=$T/bin:$PATH LENNOX_SUDO= LENNOX_STATE=$T/state LENNOX_PARTUUID_DIR=$T/partuuid"
out="$($EC bash $TOOL clean)"
check "clean (no --yes) lists the dead ones" "grep -q 'Boot0000' <<<\"\$out\" && grep -q 'Boot0002' <<<\"\$out\" && grep -q 'Boot000D' <<<\"\$out\" && grep -q 'Boot0011' <<<\"\$out\""
check "clean never lists Windows, rEFInd, firmware or USB" "! grep -qE 'Boot(000F|0012|001C|9999)' <<<\"\$out\""
check "clean without --yes removes nothing" "[ ! -s $T/calls ] 2>/dev/null || ! grep -q -- '-B' $T/calls"
: > "$T/calls"; $EC bash "$TOOL" clean --yes >/dev/null
check "clean --yes removes exactly the dead ones" "[ \"\$(grep -c -- '-B -b' $T/calls)\" = 4 ] && grep -q -- '-B -b 0000' $T/calls && grep -q -- '-B -b 0011' $T/calls && ! grep -q -- '-b 000F\|-b 0012\|-b 9999\|-b 001C' $T/calls"
check "clean saved a backup first" "ls $T/state/efi-backup-*before-clean.txt >/dev/null 2>&1"
rm -rf "$T/partuuid"; mkdir "$T/partuuid"
check "can't read partitions: removes nothing" "! $EC bash $TOOL clean --yes 2>&1 | grep -q Removed"
rm -rf "$T"

check "does not use mountpoint (it needs to open /boot/.., which only root may)" "! grep -q 'mountpoint -q' $TOOL"
exit $fail
