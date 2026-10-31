# What's new in Lennox

Newest first. After `lennox upgrade` you get a notification with the
highlights, and Lennox Settings > About lists everything.

## 1.13.0 · 2026-10-31 · Copy text, lighter in the background

- SUPER + SHIFT + O: drag a box around any text on the screen (a video, an image, a game) and it lands in your clipboard, in English and Arabic
- Lighter in the background: the island checks Wi-Fi, Bluetooth, mic and Do not disturb every 6 seconds instead of every 2, and the clip, battery and live wallpaper watchers no longer start Python each time. Less battery used while idle

## 1.12.1 · 2026-10-31 · Fixes

- Laggy or cutting-out Bluetooth headphones: Lennox Settings > Sound > Check finds the cause (2.4 GHz Wi-Fi, Wi-Fi power saving, call mode), and Smooth it fixes the rest
- Smooth it keeps the headphones awake between sounds and turns off Wi-Fi and Bluetooth power saving

## 1.12.0 · 2026-10-31 · Arabic keyboard

- An Arabic keyboard switch in Lennox Settings > Keyboard & Touchpad: adds Arabic next to your layout
- Switch with Alt + Shift (or the shortcut you chose); the bar shows which layout is on

## 1.11.1 · 2026-10-30 · Fixes

- Fixed: the mouse cursor was missing when screen sharing on Discord (and in recordings)

## 1.11.0 · 2026-10-30 · Live wallpapers

- Live wallpapers: pick a video in Lennox Settings > Wallpaper and it plays behind your windows, without sound
- It pauses in games, in fullscreen, on the lock screen and (if you like) on battery
- Colors, the lock screen and the login screen use a still frame of it; GIF wallpapers move too
- Upgrades now also install new AUR packages
- Fixed: backups now include the current wallpaper

## 1.10.0 · 2026-10-30 · Lock screen widgets

- The lock screen shows what's playing, your next alarm or timer, the weather, your phone's battery and who's on the Minecraft server
- The date sits above the clock; media keys still work while locked
- Lennox Settings > Widgets > Lock screen turns each line on or off

## 1.9.0 · 2026-10-30 · Window overview

- SUPER + TAB opens a window overview: every window on every workspace, grouped, with previews
- Type to search, arrows and Enter or a click to jump there, Esc closes; minimized windows come back too
- The old window list moved to SUPER + SHIFT + TAB

## 1.8.0 · 2026-10-30 · Settings backup

- Lennox Settings > Backup: your settings, tweaks, alarms, focus and sleep stats and wallpaper in one small file
- Back up to the Windows drive, a USB stick or a cloud folder, now or every week, keeping the newest 5
- Restore with one button, or right after a reinstall: ./install.sh --restore FILE

## 1.7.0 · 2026-10-30 · Smart bedtime

- Smart bedtime learns when you really stop at night and suggests a bedtime that actually catches you
- Turn it on and it moves the bedtime by itself, 15 minutes earlier each week you keep to it, until your goal
- The weekly sleep summary includes the suggestion; Lennox Settings > Night has a Use it button
- Time pickers now go in 15-minute steps

## 1.6.0 · 2026-10-30 · Sound effects

- Soft UI sounds for notifications, volume keys, screenshots, plugging in, Bluetooth devices and locking
- Notification sounds stay quiet in Do not disturb, focus and game mode
- Lennox Settings > Sound > Sound effects: a volume, a switch for each kind, and a login sound if you like

## 1.5.0 · 2026-10-30 · Focus mode

- Focus mode (SUPER + F12, the quick panel or the island): 25, 50 or 90 minute sessions, then a short break
- While focusing, Discord, Vesktop and Steam close, YouTube, TikTok and other distracting sites don't load, and notifications wait
- The island counts down, with +5 min and Stop
- Lennox Settings > Focus: what gets blocked, session and break length, and your focus today, this week and your streak

## 1.4.0 · 2026-10-30 · Easy apps & phone

- App Store in Lennox Settings: Arch, the AUR and Flathub in one search, with Install, Update and Remove
- Phone link (KDE Connect): pair your phone, see its battery, ring it, send files and the clipboard
- Cleanup page: frees old downloads, unused packages, logs and old trash, and shows the space freed
- A quiet weekly cleanup of your own files (trash, thumbnails, AUR build files)
- The dynamic island is smaller and cleaner, and big album covers no longer blow it up
- Versions and this "What's new": a notice after every upgrade (lennox version, lennox news)

## 1.3.0 · 2026-10-30 · Gaming, clips, island and clock

- Dynamic island in the middle of the bar: music, timers, calls, notifications, charging
- Clock app (SUPER + ALT + C): timers, alarms, stopwatch, reminders and a world clock
- Clip recorder: SUPER + ALT + R saves the last 2 minutes of a game, with a vertical TikTok copy
- Game Center page: launchers, FPS overlay (MangoHud), clips and performance modes
- Performance modes (Quiet / Balanced / Max) in the bar and on SUPER + ALT + P
- Minecraft server in the bar: players online, ping, and a notice when someone joins

## 1.2.0 · 2026-10-30 · Panels & health

- System monitor in the bar: temperatures and load, with a live tooltip
- AI coding spend in the bar with a monthly budget and warnings (CodeBurn)
- Sleep wind-down at bedtime: warmer, dimmer, quieter, with weekly sleep stats
- Opens Windows (NTFS) drives and exFAT USB sticks
- Token-saving Claude Code rules in ~/.claude/CLAUDE.md

## 1.1.0 · 2026-10-29 · Passwords, windows and sound

- Passwords: Bitwarden, and SUPER + P fills logins anywhere
- Stacking windows (SUPER + SHIFT + T) and minimize buttons in apps
- The quick panel shows the real Wi-Fi, Bluetooth and brightness state
- Sound: a deep driver check, a clean microphone, Bluetooth that stays in full quality, outputs that stop jumping

## 1.0.0 · 2026-10-28 · First release

- Hyprland with a Lua config, the Lennox bar and launcher, and Lennox Settings
- Desktop widgets, a dashboard (SUPER + D), color themes and a wallpaper pack
- NVIDIA (GTX 1650) set up for games, automatic system updates and snapshots
