# Lennox

**Hyprland for Arch Linux, in the spirit of [ML4W](https://ml4w.com/os/).**
Clean, minimal, and one place to control everything.

Lennox starts from ML4W's foundations (the wallpapers, lock screen, login screen, keybindings and colors generated from your wallpaper) and gives it its own face:

- **The Lennox bar**: three floating glass islands (or one slim strip). Workspaces are dots; the one you're on stretches into a numbered pill with a springy animation. The clock opens the dashboard, the star opens your apps.
- **The Lennox launcher** (`SUPER + SPACE`): a glass card with your wallpaper, a greeting, a big search pill and a grid of apps. It pops in; the bar slides down; the quick panel slides in from the side.

On top of that it adds:

- **Lennox Settings** (`SUPER + I`): a real settings app for the whole desktop. Appearance, wallpaper, bar and dock, sound and microphone, display, keyboard and touchpad, Wi-Fi and Bluetooth, power and battery, night light, graphics (NVIDIA), default apps, updates, keybindings, and a health check.
- **Dashboard** (`SUPER + D`) and **desktop widgets**: a sidebar with quick actions, volume and brightness, music, weather, calendar, system stats and notes, plus a big clock, weather and now-playing on your wallpaper. All colored from your wallpaper.
- **Color themes**: 12 themes (Ocean, Sakura, Sunset, Forest, Lavender, Midnight…) or colors picked from your wallpaper.
- **More wallpapers**: the Lennox pack, 12 wallpapers painted on your machine (aurora, sunset beach, night sky, dunes, clouds…), plus the 13 ML4W ones and an optional 200+ ML4W collection.
- **Minimize** (`SUPER + H`): windows wait on a hidden workspace; a bar button shows how many and brings them back. The minimize button inside apps works too.
- **One-click looks**: Lennox, Glass, Neon (spinning border), Minimal, Focus, Lightweight and ML4W Classic, plus animation styles (Dynamic, Moving, Classic…).
- **Quick panel** (`SUPER + N`): phone-style toggles (Wi-Fi, Bluetooth, mic, night light, game mode, stay awake, battery saver, dark mode), volume / mic / brightness sliders, media controls and notifications.
- **Hybrid NVIDIA done right** for laptops like yours (Intel + GTX 1650). The desktop runs on Intel so the GTX can power off, and games and Minecraft use the GTX. External screens on NVIDIA ports are switched on automatically.
- **Drivers that keep themselves up to date.** NVIDIA, sound and mic firmware, touchpad, Wi-Fi and the kernel update automatically, with safety checks: only on the charger, never on a phone hotspot, paused when Arch news says an update needs a manual step, a btrfs snapshot first, and the NVIDIA driver verified before you restart.
- **Night owl friendly.** Automatic night light and an optional wind-down reminder.

> Lennox targets the current Hyprland **Lua** config (Hyprland 0.55+; tested against the API of 0.56 on Arch and 0.57).

## Install

New to Arch? Follow **[docs/INSTALL-ARCH.md](docs/INSTALL-ARCH.md)**: it walks through installing Arch with the right options (btrfs + GRUB, so updates can always be undone).
Already installed Arch? Follow **[docs/AFTER-INSTALL.md](docs/AFTER-INSTALL.md)**: the full tutorial from the first text screen to a finished desktop.

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
| `SUPER + D` | Dashboard |
| `SUPER + W` | Pick a wallpaper (the whole desktop re-colors) |
| `SUPER + Q` | Close a window |
| `SUPER + 1…0` | Workspaces (or swipe with 3 fingers) |
| `SUPER + CTRL + K` | Search every shortcut |

All shortcuts: [docs/KEYBINDINGS.md](docs/KEYBINDINGS.md).

## What's inside

| Part | Tool |
| --- | --- |
| Compositor | Hyprland (Lua config) with `hypridle`, `hyprlock`, `hyprsunset` |
| Bar | Waybar: Lennox Islands / Lennox Line (plus the classic ML4W bars) |
| Launcher and menus | rofi, Lennox glass theme (apps grid, clipboard, Wi-Fi, emoji, wallpapers, power) |
| Font | Inter |
| Quick panel and notifications | SwayNotificationCenter |
| Dashboard and desktop widgets | Python + GTK4 + gtk4-layer-shell |
| Dock | nwg-dock-hyprland |
| Colors | matugen (Material You from the wallpaper), `awww` for wallpapers |
| Login | SDDM with the ML4W theme, showing your wallpaper |
| Terminal | kitty + zsh + Oh My Posh, fastfetch |
| Apps | Zen Browser, Nautilus, Vesktop, Steam, Prism Launcher, VS Code, IntelliJ |
| Bar extras | Temperatures with a live tooltip (`lennox-sysmon`), AI coding spend with a monthly budget (`lennox-aispend`, needs `codeburn`) |
| Clock & island | Clock app (timers, alarms, stopwatch, reminders, world clock) and a dynamic island under the bar (`lennox-clock`) |
| Gaming | Game Center in Settings: clips with a vertical TikTok copy (`lennox-clips`, `SUPER + ALT + R`), performance modes (`lennox-perf`), FPS overlay (MangoHud), Minecraft server in the bar (`lennox-mcserver`) |
| Sound effects | Soft UI sounds for notifications, volume, screenshots, charging, devices and locking (`lennox-sound-fx`) |
| Lock screen | Music, next alarm, weather, phone battery and server players on the lock screen (`lennox-lockinfo`) |
| Window overview | `SUPER + TAB`: every window with a preview, type to search (`lennox-overview`) |
| Focus | Focus mode (`SUPER + F12`): timed sessions that close distracting apps, block sites and hold notifications, with a break and daily stats (`lennox-focus`) |
| Sleep | Wind-down at bedtime (warmer, dimmer, quiet, reminders) and weekly sleep stats (`lennox-winddown`), smart bedtime that adapts to when you really stop (`lennox-bedtime`) |
| Apps & phone | App Store page (Arch, AUR and Flathub in one search; `lennox-apps`), phone link with KDE Connect (`lennox-phone`) |
| Backup | Settings, tweaks, alarms, stats and wallpaper backed up weekly to a drive of your choice; `./install.sh --restore FILE` after a reinstall (`lennox-backup`) |
| Cleanup | One button and a weekly run free old downloads, unused packages, logs and trash (`lennox-cleanup`) |
| Passwords | Bitwarden (app, Zen add-on, phone), `SUPER + P` filler with rbw + rofi-rbw |
| Settings app | Python + GTK4 / libadwaita |

Your files:

- `~/.config/lennox/settings.json`: every setting (Lennox Settings writes it; `lennox get` / `lennox set` from a terminal).
- `~/.config/hypr/custom.lua`: your own Hyprland tweaks. Loaded last, never overwritten.
- `~/.config/zshrc/90-custom`, `~/.config/kitty/custom.conf`: your own shell and terminal tweaks.
- `~/.claude/CLAUDE.md`: your Claude Code rules (token-saving defaults). Installed once; your edits are never overwritten.

## Versions

`lennox version` shows yours. After `lennox upgrade` a notification lists what's new, and
Lennox Settings > About shows every change ([changelog](dotfiles/.local/share/lennox/CHANGELOG.md),
also `lennox news`).

## Something wrong?

Run `lennox doctor` (or Lennox Settings > Health Check). It checks the NVIDIA and Intel drivers, sound and microphone, touchpad, network, updates and the desktop, and tells you how to fix anything it finds. More in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Credits

Lennox is built on the ideas, layout, lock screen, SDDM theme and wallpapers of **[ML4W OS](https://github.com/mylinuxforwork/dotfiles)** by Stephan Raabe. The ML4W wallpapers and login theme are downloaded from the ML4W repositories during installation. Like ML4W, Lennox is free software under the [GPL-3.0](LICENSE).
