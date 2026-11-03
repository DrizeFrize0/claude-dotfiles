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

T="$(mktemp -d)"; mkdir -p "$T/etc" "$T/bin" "$T/theme"; printf 'HOOKS=(base udev)\n' > "$T/etc/mkinitcpio.conf"
check "unknown boot loader: stops, changes nothing" "! env PATH=\"$T/bin:\$PATH\" LENNOX_ROOT=$T LENNOX_SUDO= PLYMOUTH_THEME_SRC=$T/theme bash $TOOL enable --yes >/dev/null 2>&1 && ! grep -q plymouth $T/etc/mkinitcpio.conf"
rm -rf "$T"
exit $fail
