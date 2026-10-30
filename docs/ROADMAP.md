# Lennox roadmap

Planned releases, in order. Each one is built, tested and pushed on its own,
bumps the version (`lennox/__init__.py`) and adds an entry at the top of
[the changelog](../dotfiles/.local/share/lennox/CHANGELOG.md), which users
see after `lennox upgrade`.

## Release 1: Panels & health (done)

System monitor in the bar, AI spend widget with a monthly budget, sleep
wind-down at 23:00 with weekly sleep stats.

## Release 2: Gaming & clips + island and clock (done)

- **Dynamic island:** a pill at the top of the screen that grows to show
  what's happening, then shrinks back: music playing, timers counting down,
  notifications, recording, charging, calls (done; volume / brightness keep
  their own pop-up, as chosen).
- **Clock app:** world clock, timers, stopwatch, alarms and reminders
  ("in 20 minutes", "at 18:00, check the server"), shown in the island and
  the bar, still firing after a restart.
- **Clip recorder:** keeps the last 2 minutes, only while gaming (game mode
  or a fullscreen game), one key saves it, plus a vertical 9:16 copy for
  TikTok / Shorts. NVIDIA encoder, so no FPS drop. Save key: SUPER + ALT + R.
- **Game center:** one panel to launch Steam / Minecraft / Prism, FPS and
  temperature overlay (MangoHud), run on the NVIDIA GPU, game mode, clips.
- **Performance modes:** Quiet / Balanced / Max in one click, with a bar
  indicator (builds on the existing power profiles in game and battery mode).
- **Minecraft server widget:** online / offline, players online with names,
  ping, a notification when someone joins. Server: vetosmp.net.

## Release 3: Easy apps & phone (done)

- **App Store:** one search over Arch, the AUR and Flathub, Install /
  Update / Remove in one click (a small window for the password).
- **Phone link:** KDE Connect, with a Phone page to pair, see the battery,
  ring it, send files and the clipboard.
- **Auto cleanup:** old package downloads, unused packages, logs over
  200 MB, AUR build files, unused Flatpak runtimes, old trash and
  thumbnails; one button with the space freed, plus a weekly run.

## Release 4: Focus, looks & polish

- **Focus mode (new):** one key (SUPER + F12) or the quick panel starts a
  focus session (25 / 50 / 90 min or until stopped). It blocks chosen apps
  and sites (Discord, TikTok, YouTube…), mutes notifications (saved for
  later), shows a countdown in the island, and plays a soft sound at the
  end with a 5-minute break. Focus stats per day / week on the Night page,
  and it turns itself off in game mode.
- **Animated wallpapers:** video / live wallpapers that pause in games,
  fullscreen and on battery; colors still follow the wallpaper.
- **Lock screen widgets:** music with controls, weather, next alarm, phone
  battery and Minecraft server players on the lock screen.
- **Window overview:** SUPER + TAB shows every window on every workspace
  with live previews; type to search, click to jump.
- **UI sounds:** soft sounds for notifications, volume, screenshots,
  plugging in and the lock screen, with a volume and an off switch.
- **Gym log (recommended):** a widget to log sets in two taps, showing last
  session's numbers to beat and the bodyweight trend (progressive overload
  plus the calorie surplus check).
- **Smart bedtime (recommended):** the wind-down learns when you actually
  fall asleep and suggests a better bedtime.
- **Settings backup (recommended):** one switch keeps settings, keybinds,
  wallpapers and clips' list backed up, restored by the installer.

## Ideas offered, not yet asked for

- Date & time page in Lennox Settings (time zone picker, 12/24 hour,
  internet sync), so the clock never needs the terminal.
