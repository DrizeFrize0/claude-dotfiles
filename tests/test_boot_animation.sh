#!/usr/bin/env bash
# lennox-boot-animation against a fake system: plan changes nothing, enable edits the
# fake files once and keeps backups, disable puts them back. Run: bash tests/test_boot_animation.sh
set -u
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SP/../dotfiles/.local/bin/lennox-boot-animation"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }

run_case() {   # run_case NAME LOADER(grub|sdboot)
    local name="$1" loader="$2" T; T="$(mktemp -d)"
    mkdir -p "$T/etc/default" "$T/boot/loader/entries" "$T/bin" "$T/theme" "$T/boot/grub"
    printf 'MODULES=()\nHOOKS=(base udev autodetect modconf block filesystems fsck)\n' > "$T/etc/mkinitcpio.conf"
    if [[ $loader == grub ]]; then
        printf 'GRUB_CMDLINE_LINUX_DEFAULT="loglevel=3"\n' > "$T/etc/default/grub"
    else
        printf 'title Arch\noptions root=/dev/sda2 rw\n' > "$T/boot/loader/entries/arch.conf"
    fi
    for c in pacman grub-mkconfig mkinitcpio plymouth; do printf '#!/bin/sh\necho "$0 $@" >> %s/calls\n' "$T" > "$T/bin/$c"; chmod +x "$T/bin/$c"; done
    printf '#!/bin/sh\necho "$0 $@" >> %s/calls\n[ -n "$1" ] && exit 0; cat %s/theme-name 2>/dev/null\n' "$T" "$T" > "$T/bin/plymouth-set-default-theme"; chmod +x "$T/bin/plymouth-set-default-theme"
    local env=(env PATH="$T/bin:$PATH" LENNOX_ROOT="$T" LENNOX_SUDO= PLYMOUTH_THEME_SRC="$T/theme")
    local before; before="$(cat "$T/etc/mkinitcpio.conf")"

    check "$name: refuses without --yes" "! ${env[*]} bash $TOOL enable >/dev/null 2>&1"
    "${env[@]}" bash "$TOOL" plan >/dev/null
    check "$name: plan changes nothing" "[ \"\$(cat $T/etc/mkinitcpio.conf)\" = \"\$before\" ]"
    "${env[@]}" bash "$TOOL" enable --yes >/dev/null 2>&1
    check "$name: hook added after udev" "grep -q 'udev plymouth' $T/etc/mkinitcpio.conf"
    check "$name: backup of mkinitcpio" "[ -f $T/etc/mkinitcpio.conf.lennox-backup ]"
    if [[ $loader == grub ]]; then
        check "$name: splash in grub" "grep -q 'quiet splash' $T/etc/default/grub"
        check "$name: grub rebuilt" "grep -q grub-mkconfig $T/calls"
    else
        check "$name: splash in entry" "grep -q 'quiet splash' $T/boot/loader/entries/arch.conf"
    fi
    check "$name: theme set and initramfs rebuilt" "grep -q 'plymouth-set-default-theme -R lennox' $T/calls"
    "${env[@]}" bash "$TOOL" enable --yes >/dev/null 2>&1
    check "$name: second run adds nothing twice" "[ \"\$(grep -o plymouth $T/etc/mkinitcpio.conf | wc -l)\" = 1 ] && [ \"\$(grep -o splash $T/etc/default/grub $T/boot/loader/entries/arch.conf 2>/dev/null | wc -l)\" -le 1 ]"
    "${env[@]}" bash "$TOOL" disable --yes >/dev/null 2>&1
    check "$name: disable restores the files" "[ \"\$(cat $T/etc/mkinitcpio.conf)\" = \"\$before\" ]"
    rm -rf "$T"
}
run_case grub grub
run_case sdboot sdboot

# Arch with one boot file (UKI), like the real laptop: the options live in /etc/kernel/cmdline
uki_case() {   # uki_case NAME STYLE(file|dir|none)
    local name="$1" style="$2" T; T="$(mktemp -d)"
    mkdir -p "$T/etc/mkinitcpio.d" "$T/etc/default" "$T/bin" "$T/theme" "$T/boot"
    printf 'HOOKS=(base udev autodetect modconf block filesystems fsck)\n' > "$T/etc/mkinitcpio.conf"
    printf 'default_uki="/boot/EFI/Linux/arch-linux.efi"\n' > "$T/etc/mkinitcpio.d/linux.preset"
    printf 'GRUB_CMDLINE_LINUX_DEFAULT="loglevel=3"\n' > "$T/etc/default/grub"          # GRUB leftovers must not matter
    printf 'BOOT_IMAGE=/vmlinuz-linux root=UUID=abc rootflags=subvol=@ rw initrd=\\initramfs-linux.img\n' > "$T/proc-cmdline"
    case "$style" in
        file) mkdir -p "$T/etc/kernel"; printf 'root=UUID=abc rw rootflags=subvol=@\n' > "$T/etc/kernel/cmdline" ;;
        dir) mkdir -p "$T/etc/cmdline.d"; printf 'root=UUID=abc rw\n' > "$T/etc/cmdline.d/root.conf" ;;
        both) mkdir -p "$T/etc/cmdline.d" "$T/etc/kernel"; printf 'root=UUID=abc rw\n' > "$T/etc/cmdline.d/root.conf"
              printf 'root=UUID=abc rw\n' > "$T/etc/kernel/cmdline" ;;
    esac
    # A fake mkinitcpio: the boot file's options come from cmdline.d first, else /etc/kernel/cmdline, else the running ones
    printf '#!/bin/sh\nif [ -n "$(ls %s/etc/cmdline.d/*.conf 2>/dev/null)" ]; then cat %s/etc/cmdline.d/*.conf; elif [ -f %s/etc/kernel/cmdline ]; then cat %s/etc/kernel/cmdline; else cat %s/proc-cmdline; fi > %s/uki-cmdline\n' "$T" "$T" "$T" "$T" "$T" "$T" > "$T/bin/mkinitcpio"
    printf '#!/bin/sh\ncat %s/uki-cmdline 2>/dev/null\n' "$T" > "$T/bin/objcopy"
    chmod +x "$T/bin/mkinitcpio" "$T/bin/objcopy"
    cp "$T/proc-cmdline" "$T/uki-cmdline"
    for c in pacman grub-mkconfig plymouth; do printf '#!/bin/sh\necho "$0 $@" >> %s/calls\n' "$T" > "$T/bin/$c"; chmod +x "$T/bin/$c"; done
    printf '#!/bin/sh\necho "$0 $@" >> %s/calls\n[ "$1" = -R ] && %s/bin/mkinitcpio\n[ -n "$1" ] && exit 0\n' "$T" "$T" > "$T/bin/plymouth-set-default-theme"; chmod +x "$T/bin/plymouth-set-default-theme"
    local env=(env PATH="$T/bin:$PATH" LENNOX_ROOT="$T" LENNOX_SUDO= PLYMOUTH_THEME_SRC="$T/theme" LENNOX_PROC_CMDLINE="$T/proc-cmdline" LENNOX_UKI_FILE="$T/uki.efi")
    check "$name: detected as a single boot file, not GRUB" "${env[*]} bash $TOOL plan | grep -q 'Boot loader: uki'"
    "${env[@]}" bash "$TOOL" enable --yes >/dev/null 2>&1
    local all; all="$(cat "$T/etc/kernel/cmdline" "$T"/etc/cmdline.d/*.conf 2>/dev/null)"
    check "$name: splash added to the kernel options" "grep -qw splash <<<\"\$all\" && grep -qw quiet <<<\"\$all\""
    check "$name: the REBUILT boot file really contains quiet and splash" "grep -qw splash $T/uki-cmdline && grep -qw quiet $T/uki-cmdline && grep -q 'root=UUID=abc' $T/uki-cmdline"
    check "$name: root= kept" "grep -q 'root=UUID=abc' <<<\"\$all\""
    check "$name: GRUB file untouched" "! grep -q splash $T/etc/default/grub"
    check "$name: plymouth hook and rebuild" "grep -q 'udev plymouth' $T/etc/mkinitcpio.conf && grep -q 'plymouth-set-default-theme -R lennox' $T/calls"
    "${env[@]}" bash "$TOOL" enable --yes >/dev/null 2>&1
    check "$name: second run adds nothing twice" "! grep -q 'splash.*splash' $T/etc/kernel/cmdline $T/etc/cmdline.d/*.conf 2>/dev/null"
    "${env[@]}" bash "$TOOL" disable --yes >/dev/null 2>&1
    all="$(cat "$T/etc/kernel/cmdline" "$T"/etc/cmdline.d/*.conf 2>/dev/null)"
    check "$name: disable removes splash" "! grep -qw splash <<<\"\$all\""
    [[ "$style" == none ]] && check "$name: disable removes the file it created" "[ ! -f $T/etc/kernel/cmdline ]"
    rm -rf "$T"
}
uki_case "uki cmdline file" file
uki_case "uki cmdline.d" dir
uki_case "uki no cmdline file" none
uki_case "uki both places" both

T="$(mktemp -d)"; mkdir -p "$T/etc" "$T/bin" "$T/theme"; printf 'HOOKS=(base udev)\n' > "$T/etc/mkinitcpio.conf"
check "unknown boot loader: stops, changes nothing" "! env PATH=\"$T/bin:\$PATH\" LENNOX_ROOT=$T LENNOX_SUDO= PLYMOUTH_THEME_SRC=$T/theme bash $TOOL enable --yes >/dev/null 2>&1 && ! grep -q plymouth $T/etc/mkinitcpio.conf"
rm -rf "$T"
exit $fail
