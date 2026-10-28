#!/usr/bin/env bash
#  _
# | |    ___ _ __  _ __   _____  __
# | |   / _ \ '_ \| '_ \ / _ \ \/ /
# | |__|  __/ | | | | | | (_) >  <
# |_____\___|_| |_|_| |_|\___/_/\_\
#
# Lennox installer: Hyprland for Arch, in the spirit of ML4W.
#
# Run it as your normal user (not root) on Arch with internet:
#   ./install.sh            install everything (asks a few questions)
#   ./install.sh --yes      install everything with the default answers
#   ./install.sh --update   refresh Lennox files after `git pull` (used by `lennox upgrade`)
#
# Safe to run again. Everything it replaces in your home folder is backed
# up to ~/.local/share/lennox/backups/<date>/ first.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES="$REPO/dotfiles"
SETUP="$REPO/setup"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/lennox"
BACKUP="$HOME/.local/share/lennox/backups/$(date +%Y-%m-%d_%H-%M-%S)"
LOGFILE="$STATE/install.log"

ASSUME_YES=false
MODE="install"
WANT_GAMING=true
WANT_DISCORD=true
WANT_DEV=true
WANT_AUR=true
WARNINGS=()

# Files you own: never overwritten once they exist
KEEP_IF_EXISTS=(
    .config/lennox/settings.json
    .config/hypr/monitors.lua
    .config/hypr/workspaces.lua
    .config/kitty/custom.conf
    .config/zshrc/90-custom
    # generated from your settings and wallpaper (regenerated at the end)
    .config/hypr/colors.lua
    .config/hypr/colors.conf
    .config/hypr/lennox/settings.lua
    .config/hypr/hypridle.conf
    .config/hypr/hyprsunset.conf
    .config/lennox/colors.json
    .config/waybar/colors.css
    .config/swaync/colors.css
    .config/nwg-dock-hyprland/colors.css
    .config/gtk-3.0/colors.css
    .config/gtk-4.0/colors.css
    .config/gtk-3.0/settings.ini
    .config/gtk-4.0/settings.ini
    .config/rofi/colors.rasi
    .config/kitty/colors-matugen.conf
    .config/kitty/lennox-settings.conf
    .config/btop/themes/lennox.theme
    .config/qt6ct/qt6ct.conf
    .config/qt6ct/colors/lennox.conf
)

# ---------------------------------------------------------------- output

bold=$'\e[1m'; dim=$'\e[2m'; green=$'\e[32m'; yellow=$'\e[33m'; red=$'\e[31m'; cyan=$'\e[36m'; reset=$'\e[0m'

step() { echo; echo "${bold}${cyan}==>${reset}${bold} $*${reset}"; }
ok()   { echo "    ${green}✓${reset} $*"; }
note() { echo "    ${dim}$*${reset}"; }
warn() { echo "    ${yellow}!${reset} $*"; WARNINGS+=("$*"); }
die()  { echo; echo "${red}${bold}✗ $*${reset}"; echo "  Full log: $LOGFILE"; exit 1; }

ask() {
    # ask "Question" Y|N  -> returns 0 for yes
    local question="$1" default="$2" reply hint="[Y/n]"
    [[ "$default" == "N" ]] && hint="[y/N]"
    if $ASSUME_YES; then
        [[ "$default" == "Y" ]]
        return
    fi
    read -rp "    ${bold}?${reset} $question $hint " reply </dev/tty
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

usage() {
    sed -n '9,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

# ---------------------------------------------------------------- arguments

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes) ASSUME_YES=true ;;
        --update) MODE="update"; ASSUME_YES=true ;;
        --no-aur) WANT_AUR=false ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
    shift
done

mkdir -p "$STATE"
exec > >(tee -a "$LOGFILE") 2>&1

# ---------------------------------------------------------------- helpers

pkg_list() {
    # pkg_list FILE...: package names without comments
    grep -hv '^\s*#' "$@" | sed 's/#.*//' | awk 'NF { print $1 }' | sort -u
}

pacman_install() {
    # Install official packages. --ask 4 lets pacman replace conflicting
    # packages (e.g. pulseaudio -> pipewire-pulse, nvidia -> nvidia-open-dkms).
    sudo pacman -S --needed --noconfirm --ask 4 "$@"
}

installed() { pacman -Q "$1" >/dev/null 2>&1; }

install_system_file() {
    # install_system_file RELATIVE_PATH MODE
    sudo install -D -m "$2" "$SETUP/system/$1" "/$1"
}

# ---------------------------------------------------------------- steps

preflight() {
    step "Checking your system"
    [[ $EUID -ne 0 ]] || die "Run this as your normal user, not root (it uses sudo when needed)."
    command -v pacman >/dev/null || die "This installer is for Arch Linux."
    [[ -d "$DOTFILES" ]] || die "Run install.sh from inside the Lennox folder."
    curl -fsS --max-time 15 -o /dev/null https://archlinux.org || die "No internet connection. Connect first (nmtui), then run again."
    ok "Arch Linux, online"

    echo "    Lennox needs sudo for system packages, drivers and services."
    sudo -v || die "sudo is needed."
    # Keep sudo alive for the whole install
    ( while kill -0 "$$" 2>/dev/null; do sudo -n true; sleep 50; done ) 2>/dev/null &
    ok "sudo ready"
}

choose() {
    step "A few questions (Enter = yes)"
    ask "Gaming: Steam, Prism Launcher (Minecraft), GameMode, MangoHud?" Y || WANT_GAMING=false
    ask "Discord (Vesktop, with working screen share)?" Y || WANT_DISCORD=false
    ask "Server dev tools: VS Code, IntelliJ, Java 21, Maven, Gradle, SFTP?" Y || WANT_DEV=false
    $WANT_AUR && { ask "Build the AUR extras (Bibata cursor, Oh My Posh prompt)?" Y || WANT_AUR=false; }
}

configure_pacman() {
    step "Configuring pacman"
    if grep -q '^#\[multilib\]' /etc/pacman.conf; then
        sudo sed -i '/^#\[multilib\]/,/^#Include/ s/^#//' /etc/pacman.conf
        ok "Enabled the multilib repository (32-bit drivers for Steam)"
    else
        ok "multilib already enabled"
    fi
    sudo sed -i 's/^#Color$/Color/' /etc/pacman.conf
    sudo sed -i 's/^#ParallelDownloads.*/ParallelDownloads = 5/' /etc/pacman.conf
    note "Updating the system first"
    sudo pacman -Sy --needed --noconfirm archlinux-keyring || die "Could not update the Arch keyring."
    sudo pacman -Su --noconfirm --ask 4 || die "System update failed. Fix the error above and run the installer again."
    ok "System up to date"
}

detect_hardware() {
    step "Detecting hardware"
    HAS_NVIDIA=false; HAS_INTEL_GPU=false; IS_LAPTOP=false
    IGPU_PCI=""; DGPU_PCI=""
    local dev class vendor
    for dev in /sys/bus/pci/devices/*; do
        class="$(cat "$dev/class")"
        [[ "$class" == 0x0300* || "$class" == 0x0302* || "$class" == 0x0380* ]] || continue
        vendor="$(cat "$dev/vendor")"
        case "$vendor" in
            0x10de) HAS_NVIDIA=true; DGPU_PCI="${dev##*/}" ;;
            0x8086) HAS_INTEL_GPU=true; IGPU_PCI="${dev##*/}" ;;
        esac
    done
    ls /sys/class/power_supply/BAT* >/dev/null 2>&1 && IS_LAPTOP=true
    $HAS_INTEL_GPU && ok "Intel graphics ($IGPU_PCI)"
    $HAS_NVIDIA && ok "NVIDIA graphics ($DGPU_PCI): $(lspci -s "$DGPU_PCI" 2>/dev/null | cut -d: -f3- | sed 's/^ //')"
    $IS_LAPTOP && ok "Laptop (battery found)"
    FS_TYPE="$(findmnt -n -o FSTYPE /)"
    BOOTLOADER="other"
    [[ -f /boot/grub/grub.cfg ]] && BOOTLOADER="grub"
    ok "Root filesystem: $FS_TYPE, bootloader: $BOOTLOADER"
}

install_packages() {
    step "Installing the desktop, drivers and apps (this takes a while)"
    local files=("$SETUP/packages/core.txt" "$SETUP/packages/desktop.txt" "$SETUP/packages/fonts.txt"
                 "$SETUP/packages/hardware.txt" "$SETUP/packages/shell.txt")
    $WANT_GAMING && files+=("$SETUP/packages/gaming.txt")
    $WANT_DEV && files+=("$SETUP/packages/dev.txt")

    mapfile -t pkgs < <(pkg_list "${files[@]}")
    note "About 1.5 GB to download. There is no progress bar here, so \"Retrieving packages...\""
    note "can sit still for 5 to 30 minutes on slower Wi-Fi. That's normal: let it run."
    pacman_install "${pkgs[@]}" || die "Package installation failed. Fix the error above and run the installer again."
    ok "${#pkgs[@]} packages installed"

    if $HAS_NVIDIA; then
        mapfile -t nv < <(pkg_list "$SETUP/packages/nvidia.txt")
        # DKMS builds the driver for every installed kernel, so each needs its headers
        local kernel
        for kernel in linux linux-lts linux-zen linux-hardened; do
            installed "$kernel" && nv+=("$kernel-headers")
        done
        pacman_install "${nv[@]}" || die "NVIDIA driver installation failed."
        ok "NVIDIA driver (nvidia-open-dkms) installed for: $(printf '%s ' "${nv[@]}" | grep -o '[a-z-]*-headers' | sed 's/-headers//g' | tr '\n' ' ')"
    fi
}

install_new_packages() {
    # After `lennox upgrade`: install packages that newer Lennox versions
    # added to the lists (already installed ones are skipped)
    step "Checking for new Lennox packages"
    local files=("$SETUP/packages/core.txt" "$SETUP/packages/desktop.txt" "$SETUP/packages/fonts.txt"
                 "$SETUP/packages/hardware.txt" "$SETUP/packages/shell.txt") missing=() p
    installed steam && files+=("$SETUP/packages/gaming.txt")
    installed maven && files+=("$SETUP/packages/dev.txt")
    while read -r p; do
        installed "$p" || missing+=("$p")
    done < <(pkg_list "${files[@]}")
    if (( ${#missing[@]} == 0 )); then
        ok "Nothing new"
    # No --ask 4 here: never swap out a package you replaced on purpose
    elif sudo pacman -S --needed --noconfirm "${missing[@]}"; then
        ok "Installed: ${missing[*]}"
    else
        warn "Could not install: ${missing[*]}. Run 'lennox update', then 'lennox upgrade' again."
    fi
}

install_aur() {
    $WANT_AUR || return 0
    step "AUR extras"
    if ! command -v yay >/dev/null && ! command -v paru >/dev/null; then
        local tmp
        tmp="$(mktemp -d)"
        if git clone --depth 1 https://aur.archlinux.org/yay-bin.git "$tmp/yay-bin" \
            && (cd "$tmp/yay-bin" && makepkg -si --noconfirm); then
            ok "yay (AUR helper) installed"
        else
            warn "Could not build yay. AUR extras skipped (the desktop works without them)."
            rm -rf "$tmp"
            return 0
        fi
        rm -rf "$tmp"
    fi
    local helper=yay
    command -v yay >/dev/null || helper=paru
    mapfile -t aur < <(pkg_list "$SETUP/packages/aur.txt")
    if "$helper" -S --needed --noconfirm --answerdiff None --answerclean None "${aur[@]}"; then
        ok "${aur[*]}"
    else
        warn "Some AUR packages failed: ${aur[*]}. Run 'yay -S ${aur[*]}' later."
    fi
}

install_flatpaks() {
    step "Flatpak apps (updated automatically with the system)"
    sudo flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo \
        || { warn "Could not add Flathub. Zen Browser / Vesktop skipped."; return 0; }
    local id pack ids=()
    while read -r id pack; do
        [[ -z "$id" || "$id" == \#* ]] && continue
        case "$pack" in
            base) ids+=("$id") ;;
            discord) $WANT_DISCORD && ids+=("$id") ;;
            dev) $WANT_DEV && ids+=("$id") ;;
        esac
    done < "$SETUP/packages/flatpak.txt"
    if sudo flatpak install --system -y --noninteractive flathub "${ids[@]}"; then
        ok "${ids[*]}"
    else
        warn "Some Flatpaks failed: ${ids[*]}. Run 'flatpak install flathub <id>' later."
    fi
}

setup_nvidia() {
    $HAS_NVIDIA || return 0
    step "NVIDIA: power saving and GPU selection"
    install_system_file etc/modprobe.d/lennox-nvidia.conf 644
    install_system_file etc/udev/rules.d/80-lennox-nvidia-pm.rules 644
    ok "The GTX can power off completely while nothing uses it"

    # Stable names for the GPUs (card0/card1 can swap between boots), used
    # by lennox-session to run the desktop on Intel.
    if [[ -n "$IGPU_PCI" && -n "$DGPU_PCI" ]]; then
        sudo tee /etc/udev/rules.d/61-lennox-gpu-paths.rules >/dev/null <<EOF
# Lennox: stable device names for the integrated and NVIDIA GPUs (made by install.sh)
KERNEL=="card*", KERNELS=="$IGPU_PCI", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/lennox-igpu"
KERNEL=="card*", KERNELS=="$DGPU_PCI", SUBSYSTEM=="drm", SUBSYSTEMS=="pci", SYMLINK+="dri/lennox-dgpu"
EOF
        sudo udevadm control --reload
        sudo udevadm trigger --subsystem-match=drm
        ok "Desktop runs on Intel; the GTX 1650 wakes up for games and external screens"
    fi
    sudo systemctl enable nvidia-persistenced.service >/dev/null 2>&1 && ok "nvidia-persistenced enabled"
}

setup_snapshots() {
    [[ "$FS_TYPE" == "btrfs" ]] || { note "Not btrfs: no snapshots (updates still check themselves before running)."; return 0; }
    step "Snapshots: an automatic restore point before every update"
    mapfile -t snap < <(pkg_list "$SETUP/packages/snapshots.txt")
    [[ "$BOOTLOADER" == "grub" ]] && snap+=(grub-btrfs inotify-tools)
    pacman_install "${snap[@]}" || { warn "Could not install snapper. Snapshots skipped."; return 0; }

    if ! sudo snapper list-configs 2>/dev/null | awk '{print $1}' | grep -qx root; then
        if mountpoint -q /.snapshots; then
            # archinstall layout: @.snapshots is its own subvolume mounted at /.snapshots
            sudo umount /.snapshots && sudo rmdir /.snapshots \
                && sudo snapper -c root create-config / \
                && sudo btrfs subvolume delete /.snapshots >/dev/null \
                && sudo mkdir /.snapshots && sudo mount -a && sudo chmod 750 /.snapshots \
                || { warn "Snapper setup failed; check 'sudo snapper list-configs'."; return 0; }
        else
            sudo snapper -c root create-config / || { warn "Snapper setup failed."; return 0; }
        fi
    fi
    sudo snapper -c root set-config TIMELINE_CREATE=no NUMBER_LIMIT=10 NUMBER_LIMIT_IMPORTANT=5 >/dev/null
    ok "snap-pac takes a snapshot before and after every update"

    if [[ "$BOOTLOADER" == "grub" ]]; then
        # Lets the read-only snapshots boot into a working desktop
        if ! grep -q 'grub-btrfs-overlayfs' /etc/mkinitcpio.conf; then
            sudo sed -i '/^HOOKS=/ s/)$/ grub-btrfs-overlayfs)/' /etc/mkinitcpio.conf
            sudo mkinitcpio -P >/dev/null || warn "mkinitcpio reported a problem; check the log."
        fi
        sudo systemctl enable --now grub-btrfsd.service >/dev/null 2>&1
        sudo grub-mkconfig -o /boot/grub/grub.cfg >/dev/null 2>&1
        ok "Snapshots appear in the GRUB boot menu (Arch Linux snapshots)"
    else
        note "Your bootloader is not GRUB: restore snapshots with Btrfs Assistant."
    fi
}

install_system_files() {
    step "Lennox system files"
    install_system_file usr/local/bin/lennox-session 755
    install_system_file usr/share/wayland-sessions/lennox.desktop 644
    install_system_file usr/local/bin/lennox-autoupdate 755
    install_system_file etc/systemd/system/lennox-autoupdate.service 644
    install_system_file etc/systemd/system/lennox-autoupdate.timer 644
    if [[ ! -f /etc/lennox/autoupdate.conf ]]; then
        install_system_file etc/lennox/autoupdate.conf 644
    fi
    sudo sed -i "s/^USER_NAME=.*/USER_NAME=$USER/" /etc/lennox/autoupdate.conf
    sudo systemctl daemon-reload
    ok "Session launcher and automatic updates installed"
}

setup_sddm() {
    step "Login screen (ML4W SDDM theme)"
    local tmp theme=/usr/share/sddm/themes/lennox
    tmp="$(mktemp -d)"
    if git clone --depth 1 https://github.com/mylinuxforwork/ml4w-sddm.git "$tmp/sddm" >/dev/null 2>&1 \
        && [[ -f "$tmp/sddm/configs/ml4w.conf" ]]; then
        sudo rm -rf "$theme"
        sudo mkdir -p "$theme"
        sudo cp -r "$tmp/sddm/." "$theme/"
        sudo rm -rf "$theme/.git"
        sudo sed 's/"ml4w\.jpg"/"lennox.jpg"/g' "$theme/configs/ml4w.conf" | sudo tee "$theme/configs/lennox.conf" >/dev/null
        sudo sed -i 's|^ConfigFile=.*|ConfigFile=configs/lennox.conf|' "$theme/metadata.desktop"
        sudo cp "$theme/backgrounds/ml4w.jpg" "$theme/backgrounds/lennox.jpg"
        # lennox-wallpaper copies your wallpaper here, so give you the folder
        sudo chown -R "$USER:$(id -gn)" "$theme/backgrounds"
        install_system_file etc/sddm.conf.d/10-lennox.conf 644
        ok "Theme installed; it follows your wallpaper"
    else
        warn "Could not download the ML4W login theme; SDDM uses its default look."
    fi
    rm -rf "$tmp"

    # Remember Lennox as the session to start
    sudo install -d -o sddm -g sddm /var/lib/sddm 2>/dev/null
    if ! sudo grep -qs 'lennox.desktop' /var/lib/sddm/state.conf; then
        printf '[Last]\nSession=/usr/share/wayland-sessions/lennox.desktop\nUser=%s\n' "$USER" \
            | sudo tee /var/lib/sddm/state.conf >/dev/null
        sudo chown sddm:sddm /var/lib/sddm/state.conf 2>/dev/null
    fi
}

enable_services() {
    step "Services"
    local dm
    for dm in gdm lightdm lxdm ly greetd; do
        if systemctl is-enabled --quiet "$dm" 2>/dev/null; then
            sudo systemctl disable "$dm" >/dev/null 2>&1 && note "Disabled $dm (SDDM replaces it)"
        fi
    done
    local svc
    for svc in NetworkManager bluetooth power-profiles-daemon sddm fstrim.timer lennox-autoupdate.timer; do
        if sudo systemctl enable "$svc" >/dev/null 2>&1; then ok "$svc"; else warn "Could not enable $svc"; fi
    done
    sudo timedatectl set-ntp true >/dev/null 2>&1
    systemctl --user enable pipewire.socket pipewire-pulse.socket wireplumber.service >/dev/null 2>&1
    ok "PipeWire sound for your user"
    # GameMode needs this group to raise game priority
    $WANT_GAMING && sudo usermod -aG gamemode "$USER" 2>/dev/null
}

install_dotfiles() {
    step "Installing Lennox into your home folder"
    mkdir -p "$BACKUP"
    local keep_file
    keep_file="$(mktemp)"
    printf '/%s\n' "${KEEP_IF_EXISTS[@]}" | grep -v '^/#' > "$keep_file"

    # Everything except the keep-list; replaced files go to the backup folder
    rsync -a --backup --backup-dir="$BACKUP" --exclude="__pycache__/" --exclude-from="$keep_file" "$DOTFILES/" "$HOME/" \
        || die "Copying the Lennox files failed."
    # The keep-list only where nothing exists yet
    rsync -a --ignore-existing --exclude='__pycache__/' --include='*/' --include-from="$keep_file" --exclude='*' "$DOTFILES/" "$HOME/"
    rm -f "$keep_file"

    if [[ -n "$(find "$BACKUP" -type f 2>/dev/null | head -n1)" ]]; then
        ok "Your previous configs are backed up in $BACKUP"
    else
        rmdir "$BACKUP" 2>/dev/null
    fi
    chmod +x "$HOME"/.local/bin/lennox* 2>/dev/null
    echo "$REPO" > "$HOME/.config/lennox/repo"
    git -C "$REPO" describe --tags --always 2>/dev/null > "$HOME/.config/lennox/version" || echo "1.0.0" > "$HOME/.config/lennox/version"
    ok "Configs and lennox-* commands installed"
}

download_wallpapers() {
    step "Wallpapers (the ML4W collection)"
    local dir="$HOME/.config/lennox/wallpapers" tmp
    mkdir -p "$dir"
    if [[ -f "$dir/default.jpg" ]]; then
        ok "Already there"
        return 0
    fi
    tmp="$(mktemp -d)"
    if git clone --depth 1 --filter=blob:none --sparse https://github.com/mylinuxforwork/dotfiles.git "$tmp/ml4w" >/dev/null 2>&1 \
        && git -C "$tmp/ml4w" sparse-checkout set dotfiles/.config/ml4w/wallpapers >/dev/null 2>&1 \
        && compgen -G "$tmp/ml4w/dotfiles/.config/ml4w/wallpapers/*" >/dev/null; then
        cp -n "$tmp/ml4w/dotfiles/.config/ml4w/wallpapers/"* "$dir/"
        ok "$(find "$dir" -type f | wc -l) wallpapers in $dir"
    elif git clone --depth 1 https://github.com/mylinuxforwork/wallpaper.git "$tmp/wallpaper" >/dev/null 2>&1; then
        find "$tmp/wallpaper" -maxdepth 2 -type f \( -iname '*.jpg' -o -iname '*.png' \) -exec cp -n {} "$dir/" \;
        ok "$(find "$dir" -type f | wc -l) wallpapers in $dir"
    else
        warn "Could not download the ML4W wallpapers. Using a plain gradient; add your own to $dir."
    fi
    rm -rf "$tmp"
}

setup_shell() {
    step "Terminal: zsh + Oh My Posh"
    if [[ "$(getent passwd "$USER" | cut -d: -f7)" != "/usr/bin/zsh" ]]; then
        sudo chsh -s /usr/bin/zsh "$USER" >/dev/null && ok "zsh is now your shell" || warn "Could not switch to zsh (run: chsh -s /usr/bin/zsh)"
    else
        ok "zsh already your shell"
    fi
}

personalize() {
    step "Personal settings"
    export PATH="$HOME/.local/bin:$PATH"

    # Keyboard layout from the Arch install
    local layout variant vc
    layout="$(localectl status 2>/dev/null | awk -F': *' '/X11 Layout/ {print $2}')"
    variant="$(localectl status 2>/dev/null | awk -F': *' '/X11 Variant/ {print $2}')"
    if [[ -z "$layout" ]]; then
        vc="$(localectl status 2>/dev/null | awk -F': *' '/VC Keymap/ {print $2}')"
        layout="${vc%%-*}"
        [[ "$layout" == "uk" ]] && layout="gb"
        [[ "$layout" == "n/a" || -z "$layout" ]] && layout="us"
    fi
    if [[ "$MODE" == "install" ]]; then
        lennox-set input.kb_layout "$layout" --no-apply >/dev/null
        lennox-set input.kb_variant "$variant" --no-apply >/dev/null
        lennox-set touchpad.gestures "$IS_LAPTOP" --no-apply >/dev/null
        ok "Keyboard layout: $layout${variant:+ ($variant)}"
    fi

    # Zen Browser is the default browser (first install only, so a browser
    # you picked later in Lennox Settings stays picked)
    if [[ "$MODE" == "install" ]] && flatpak info app.zen_browser.zen >/dev/null 2>&1; then
        xdg-settings set default-web-browser app.zen_browser.zen.desktop 2>/dev/null
        lennox-set apps.browser "flatpak run app.zen_browser.zen" --no-apply >/dev/null
        ok "Zen Browser is your default browser"
    fi
    # Once: installs from before the Lennox bar existed move to it (picking
    # an ML4W bar again later in Lennox Settings sticks)
    local marker="$HOME/.config/lennox/.new-bar-done"
    if [[ ! -f "$marker" ]]; then
        [[ "$(lennox-get bar.style)" == "modern" ]] && lennox-set bar.style lennox --no-apply >/dev/null \
            && ok "Switched to the new Lennox bar (the ML4W bars are still in Lennox Settings > Bar)"
        touch "$marker"
    fi
    xdg-mime default org.gnome.Nautilus.desktop inode/directory 2>/dev/null
    xdg-mime default org.gnome.Loupe.desktop image/png image/jpeg image/webp image/gif 2>/dev/null
    xdg-mime default mpv.desktop video/mp4 video/x-matroska video/webm 2>/dev/null
    xdg-mime default org.gnome.TextEditor.desktop text/plain 2>/dev/null
    xdg-user-dirs-update 2>/dev/null

    # Minecraft (Prism Launcher) on the GTX 1650
    if $HAS_NVIDIA && $WANT_GAMING; then
        local cfg="$HOME/.local/share/PrismLauncher/prismlauncher.cfg"
        mkdir -p "$(dirname "$cfg")"
        if ! grep -qs '^UseDiscreteGpu=' "$cfg"; then
            echo "UseDiscreteGpu=true" >> "$cfg"
            ok "Minecraft runs on the NVIDIA GPU (Prism Launcher)"
        fi
    fi
    $HAS_NVIDIA && note "Steam games: Proton games pick the NVIDIA GPU by themselves; for native games add 'prime-run %command%' to launch options."
}

first_theme() {
    step "Building your theme from the wallpaper"
    export PATH="$HOME/.local/bin:$PATH"
    lennox-apply --no-reload all >/dev/null 2>&1 || warn "lennox-apply reported a problem"
    if lennox-wallpaper --restore --quiet --no-reload >/dev/null 2>&1; then
        ok "Colors, lock screen and login screen match the wallpaper"
    else
        warn "Theming will finish on first login"
    fi
}

summary() {
    echo
    echo "${bold}${green}Lennox is installed.${reset}"
    if (( ${#WARNINGS[@]} )); then
        echo
        echo "${yellow}${bold}A few things to look at:${reset}"
        local w
        for w in "${WARNINGS[@]}"; do
            echo "  ${yellow}!${reset} $w"
        done
    fi
    if [[ "$MODE" == "install" ]]; then
        cat <<EOF

  After the restart, pick ${bold}Lennox (Hyprland)${reset} on the login screen.
  ${bold}SUPER + I${reset}        Lennox Settings (control everything from here)
  ${bold}SUPER + N${reset}        quick panel      ${bold}SUPER + SPACE${reset}  apps
  ${bold}SUPER + CTRL + K${reset} all shortcuts    ${bold}lennox doctor${reset}  health check

  Log: $LOGFILE
EOF
        ask "Restart now?" Y && sudo systemctl reboot
    else
        echo "  Log out and back in to load everything (or press SUPER + SHIFT + R)."
    fi
}

# ---------------------------------------------------------------- main

echo "${bold}${cyan}"
sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
echo "${reset}${dim}  Hyprland for Arch, in the spirit of ML4W   ·   log: $LOGFILE${reset}"

preflight
detect_hardware

if [[ "$MODE" == "update" ]]; then
    install_new_packages
    install_system_files
    $HAS_NVIDIA && setup_nvidia
    install_dotfiles
    personalize
    first_theme
    summary
    exit 0
fi

choose
configure_pacman
install_packages
install_aur
install_flatpaks
setup_nvidia
install_system_files
setup_snapshots
setup_sddm
enable_services
install_dotfiles
download_wallpapers
setup_shell
personalize
first_theme
summary
