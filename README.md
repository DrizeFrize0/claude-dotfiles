# Lennox

**Hyprland for Arch Linux, in the spirit of [ML4W](https://ml4w.com/os/).**
Clean, minimal, and one place to control everything.

Lennox keeps the ML4W look you know: the same wallpapers, the same lock screen and login screen, the Modern / Glass / Minimal bars, colors generated from your wallpaper (matugen), the ML4W rofi launcher and keybindings. On top of that it adds:

- **Lennox Settings** (`SUPER + I`): a real settings app for the whole desktop. Appearance, wallpaper, bar and dock, sound and microphone, display, keyboard and touchpad, Wi-Fi and Bluetooth, power and battery, night light, graphics (NVIDIA), default apps, updates, keybindings, and a health check.
- **Quick panel** (`SUPER + N`): phone-style toggles (Wi-Fi, Bluetooth, mic, night light, game mode, stay awake, battery saver, dark mode), volume / mic / brightness sliders, media controls and notifications.
- **Hybrid NVIDIA done right** for laptops like yours (Intel + GTX 1650). The desktop runs on Intel so the GTX can power off, and games and Minecraft use the GTX. External screens on NVIDIA ports are switched on automatically.
- **Drivers that keep themselves up to date.** NVIDIA, sound and mic firmware, touchpad, Wi-Fi and the kernel update automatically, with safety checks: only on the charger, never on a phone hotspot, paused when Arch news says an update needs a manual step, a btrfs snapshot first, and the NVIDIA driver verified before you restart.
- **Night owl friendly.** Automatic night light and an optional wind-down reminder.

> Lennox targets the current Hyprland **Lua** config (Hyprland 0.55+; tested against the API of 0.56 on Arch and 0.57).

## Install

New to Arch? Follow **[docs/INSTALL-ARCH.md](docs/INSTALL-ARCH.md)**: it walks through installing Arch with the right options (btrfs + GRUB, so updates can always be undone).

On an installed Arch system, as your normal user:

```sh
sudo pacman -S --needed git
git clone https://github.com/DrizeFrize0/claude-dotfiles.git ~/lennox
cd ~/lennox
./install.sh
```

It asks four yes/no questions (gaming, Discord, server dev tools, AUR extras), installs everything, backs up anything it replaces to `~/.local/share/lennox/backups/`, and offers to restart. On the login screen pick **Lennox (Hyprland)**.

Update Lennox itself later with `lennox upgrade`.

## First steps

| Keys | What |
| --- | --- |
| `SUPER + SPACE` | Apps |
| `SUPER + RETURN` | Terminal |
| `SUPER + B` / `SUPER + E` | Browser (Zen) / Files |
| `SUPER + I` | Lennox Settings |
| `SUPER + N` | Quick panel |
| `SUPER + W` | Pick a wallpaper (the whole desktop re-colors) |
| `SUPER + Q` | Close a window |
| `SUPER + 1…0` | Workspaces (or swipe with 3 fingers) |
| `SUPER + CTRL + K` | Search every shortcut |

All shortcuts: [docs/KEYBINDINGS.md](docs/KEYBINDINGS.md).

## What's inside

| Part | Tool |
| --- | --- |
| Compositor | Hyprland (Lua config) with `hypridle`, `hyprlock`, `hyprsunset` |
| Bar | Waybar, ML4W Modern / Glass / Minimal |
| Launcher and menus | rofi (apps, clipboard, Wi-Fi, emoji, wallpaper grid, power menu) |
| Quick panel and notifications | SwayNotificationCenter |
| Dock | nwg-dock-hyprland |
| Colors | matugen (Material You from the wallpaper), `awww` for wallpapers |
| Login | SDDM with the ML4W theme, showing your wallpaper |
| Terminal | kitty + zsh + Oh My Posh, fastfetch |
| Apps | Zen Browser, Nautilus, Vesktop, Steam, Prism Launcher, VS Code, IntelliJ |
| Settings app | Python + GTK4 / libadwaita |

Your files:

- `~/.config/lennox/settings.json`: every setting (Lennox Settings writes it; `lennox get` / `lennox set` from a terminal).
- `~/.config/hypr/custom.lua`: your own Hyprland tweaks. Loaded last, never overwritten.
- `~/.config/zshrc/90-custom`, `~/.config/kitty/custom.conf`: your own shell and terminal tweaks.

## Something wrong?

Run `lennox doctor` (or Lennox Settings > Health Check). It checks the NVIDIA and Intel drivers, sound and microphone, touchpad, network, updates and the desktop, and tells you how to fix anything it finds. More in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Credits

Lennox is built on the ideas, layout, lock screen, SDDM theme and wallpapers of **[ML4W OS](https://github.com/mylinuxforwork/dotfiles)** by Stephan Raabe. The ML4W wallpapers and login theme are downloaded from the ML4W repositories during installation. Like ML4W, Lennox is free software under the [GPL-3.0](LICENSE).
