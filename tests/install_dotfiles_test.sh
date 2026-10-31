#!/usr/bin/env bash
set -uo pipefail
REPO="$PWD"; DOTFILES="$REPO/dotfiles"; HOME="$1"; BACKUP="$HOME/.local/share/lennox/backups/$2"
step() { echo "== $*"; }; ok() { echo "   ok: $*"; }; die() { echo "DIE: $*"; exit 1; }
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
install_dotfiles
