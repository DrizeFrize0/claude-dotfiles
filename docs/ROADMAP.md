# Lennox roadmap

Planned releases, in order. Each one is built, tested and pushed on its own.

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

## Release 3: Easy apps & phone

App store page (Arch, AUR and Flathub in one search), phone link
(KDE Connect), auto cleanup.

## Release 4: Looks & polish

Animated wallpapers (pause in games, fullscreen and on battery), lock
screen widgets, window overview, UI sounds.

## Ideas offered, not yet asked for

- Date & time page in Lennox Settings (time zone picker, 12/24 hour,
  internet sync), so the clock never needs the terminal.
