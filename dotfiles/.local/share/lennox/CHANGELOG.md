# What's new in Lennox

Newest first. After `lennox upgrade` you get a notification with the
highlights, and Lennox Settings > About lists everything.

## 1.28.1 · 2026-11-04 · The boot menu finds your Arch file

- lennox-bootmenu now looks for your Arch boot file (like archlinux.efi) anywhere on the boot partition, and checks every FAT partition that is mounted to find the one that holds it. When it still finds nothing, it lists the .efi files that are there and tells you what to try, instead of just stopping

## 1.28.0 · 2026-11-04 · A boot menu

- New tool: lennox-bootmenu. Sets up a graphical boot menu (rEFInd) so the laptop asks whether to start Arch Linux or Windows, instead of going straight to Windows. It shows its plan first, saves your current boot entries, never touches Windows, and lennox-bootmenu disable --yes takes it out and puts the old boot order back
- It refuses to continue when it is unsafe: Secure Boot on, no Linux boot file found, or not started in UEFI mode

## 1.27.0 · 2026-11-04 · Sound that stays fixed, game mode by itself, better ping

- Bluetooth headphones no longer start in bad quality: the laptop stops offering the phone-call mode, so the headphones connect in full quality every time and you no longer need to disconnect and reconnect them. Better SBC quality is on too
- Microphone fixes for Discord: microphones are never put to sleep (a sleeping mic could wake up silent), a muted mic is switched back on at login, and the default microphone can never be a speaker loopback. A small helper watches for changes (headphones connecting, mics appearing) and puts things right
- Game mode now turns on by itself while a game is open (Steam and Proton games, Minecraft, emulators, gamescope, or names you add) and off when you close it, without touching a game mode you turned on by hand. Settings > Game Center
- Better ping: BBR and fq network settings, and Wi-Fi power saving is off. Settings > Game Center > Check my ping measures your router, the internet and your Minecraft server, and tells you what to fix (weak signal, 2.4 GHz, bumpy connection)
- The upgrade applies all of this once and restarts the sound system, so headphones may blip for a second

## 1.26.0 · 2026-11-04 · Everything in Release 5

- Extras page (Settings > Everyday) with a switch for each of these:
- Desktop pet: a small cat walks along the bottom of the screen, and sleeps while you focus, when you are away, or after 5 quiet minutes
- Music wallpaper: the bottom of the desktop pulses with what is playing, in your theme colors (uses cava, installed by the upgrade)
- Cursor effects: a glowing trail or a spotlight for screen sharing, and a ring on every click
- Lyrics in the island: synced lyrics under the song title, Arabic right to left
- Screensaver: stars, rain on glass or aurora, after a few idle minutes before the lock screen. Any key closes it
- Theme of the season: colors change for Ramadan, Eid, Halloween, New Year and Independence Day, then go back. Add pictures to a folder for a wallpaper too
- Wallpaper of the day, and profiles by Wi-Fi network or time of day (like quiet mode and low volume at school)
- Fan and noise profiles: Silent, Normal, Turbo, with the temperature and fan speed shown
- Discord: how many people are online in your server, on the desktop and the dashboard
- Downloads and the next prayer now show in the bar
- Ask Claude from anywhere with SUPER + SHIFT + A (needs an API key file, or Claude Code installed)
- Snake and Flappy for a quick break (SUPER + SHIFT + G), and a few hidden surprises
- Startup animation: a Lennox animation at boot. It only changes anything when you turn it on, and it shows you what first
- New pages: Storage (what is using the disk, biggest first, safe delete to the trash), Trophies (badges for using Lennox), Date & time (time zone, automatic time, 12 or 24 hour clock)
- Daily care now has a mood diary (one tap each evening) and a "why am I tired" report from your own sleep, mood and focus

## 1.25.0 · 2026-11-04 · Study subjects and a hello

- Focus sessions can have a subject (Math, Physics, Chemistry, English, Arabic, or your own list). Pick it on the Focus page, or start one with lennox-focus start 50 --subject=Math. The page shows this week's hours for each subject
- A friendly hello a few seconds after you log in: the weather, your next prayer and alarm, and your focus streak. Settings > Daily care > Greeting changes your name or turns it off

## 1.24.1 · 2026-11-03 · No more self-scrolling

- Pages in the browser and Discord no longer scroll by themselves. A click on the mouse wheel starts "autoscroll", and after that the page follows your mouse. Wheel clicks are now ignored. Settings > Keyboard & Touchpad > Ignore wheel clicks turns this off
- Cleaner code: the helpers that ten tools each had their own copy of now live in one place, and a few unused leftovers are gone. Nothing was removed from what Lennox does

## 1.24.0 · 2026-11-03 · Daily care

- New page: Daily care (Settings > Everyday)
- Water reminder: a gentle nudge after every hour (you choose) at the laptop. It waits while you game, focus or the screen is locked. Off until you turn it on
- Heat alerts: a warning when the processor or graphics chip stays too hot for a minute, with a one-tap button to switch to Quiet mode. On by default. The graphics chip is only checked while it is awake in a game, so this never wakes it
- Prayer times: reminders before each prayer and when it is time, with the Arabic names, worked out on the laptop without internet. Set for Amman by default; any place works. Off until you turn it on

## 1.23.0 · 2026-11-03 · Speed pass

- Fast mode: lighter blur and shadows, and windows you are not using stay solid instead of see-through, so the graphics chip does much less work. It turns on by itself when you upgrade. Settings > Power > Speed turns it off again
- The desktop no longer watches the config for edits, and no longer animates dragging and resizing windows
- New installs start with the lighter blur and shadow
- Discord (Vesktop) laggy? Settings > Power > Speed can switch it to its other window mode (and back)

## 1.22.2 · 2026-10-31 · A better rescue

- lennox-rescue now checks step by step: is the desktop running, the Hyprland version, anything holding the keyboard, the main key, parts of the config that failed to load, and whether the Windows key itself works
- It fixes what it can, and offers a safe mode with the basic shortcuts when the config is broken (lennox-rescue --undo puts the full config back)
- It saves a report to lennox-rescue-report.txt in your home folder

## 1.22.1 · 2026-10-31 · Keys rescue

- Keys not working? From a text screen (Ctrl + Alt + F3) run lennox-rescue: it frees the keyboard, resets the main key, reloads the config and shows any config errors
- Shortcuts that work without the Windows key: Alt + F2 app launcher, Alt + F4 close window, Ctrl + Alt + T terminal, Ctrl + Alt + Delete power menu
- The dashboard no longer grabs the whole keyboard, and the window overview closes itself after two minutes so it can never get stuck

## 1.22.0 · 2026-10-31 · Bar density, texture and island look

- Bar density in Settings > Bar & Dock: Compact makes the Lennox bar styles a few pixels slimmer (the island shrinks with it)
- Subtle texture: an optional faint grain on the bar for the Lennox styles
- The Islands and Line bars get a hairline highlight along the top, and status icons glow softly when you point at them
- Settings > Widgets shows how each island activity looks: its icon and its glow color
- The bar style gallery explains that the bar moves with smooth transitions because Waybar can't run looping animations

## 1.21.0 · 2026-10-31 · Island gestures and details

- Scroll on the island while music plays to change the volume; middle-click it for the next song
- Right-click the island for a small menu: hide it for an hour (alarms still come through) or open its settings
- Long song titles slide slowly across instead of being cut off (only while they don't fit)
- The album cover in the pill sits in a thin ring that fills up as the song plays
- A ringing alarm's bell shakes, and the recording dot pulses red when a clip is saved

## 1.20.0 · 2026-10-31 · Bar style gallery

- Settings > Bar & Dock now shows every bar style as a small live preview, drawn in your wallpaper's colors, instead of a plain list
- Click a preview to switch the bar to it; the one you use is outlined
- The previews show what makes each style different: Islands, Line, Aurora's glowing edge, Pills with colored icon chips, Minimal Dots and the classic ML4W styles

## 1.19.0 · 2026-10-31 · Pills and Minimal Dots bars

- New bar style, Lennox Pills: no strip, every part of the bar is its own chunky rounded pill floating over the wallpaper
- In Pills, volume, network, battery, updates and the system monitor start with a colored chip behind their icon; notifications and power are round colored buttons; pills glow softly when you point at them
- New bar style, Lennox Minimal Dots: a thin, nearly see-through strip with small dimmed text that brightens when you point at it, and workspaces as small dots (no numbers)
- Both keep the island sitting exactly in the bar
- Pick them in Settings > Bar & Dock or the bar style menu

## 1.18.0 · 2026-10-31 · Aurora bar

- New bar style, Lennox Aurora: one frosted strip with a soft glowing edge that blends your wallpaper's colors, and a thin highlight along the top
- In Aurora, the workspace you are on is a long gradient pill that slides between the dots when you switch
- The Lennox button glows when you point at it
- Pick it in Settings > Bar & Dock, the bar style menu, or with lennox bar style lennox-aurora
- Same height as the Line style, so the island still sits exactly in the bar

## 1.17.0 · 2026-10-31 · Island redesign, part 2

- Two things at once, the iPhone way: when music plays and a timer runs (or focus, a call, the stopwatch), the island splits into the pill and a small linked bubble beside it, each with its own icon, color and time
- Click the small bubble to swap: its activity moves into the big pill
- Opening the island still shows one card at a time; the bubble comes back when it closes

## 1.16.0 · 2026-10-31 · Island redesign, part 1

- The island now springs smoothly between sizes instead of jumping, and fades between what it shows (music, timer, focus, a message) instead of redrawing
- Each activity has its own soft glow ring: music in your theme color, timers amber, focus green, calls blue, recording red; a ringing alarm pulses
- New messages land with a small bounce
- Timers and focus rounds show a circular countdown ring, small in the pill and big when it opens
- A new matching icon set for everything in the island (Phosphor icons, MIT license, kept next to them)
- Nothing animates while the island is idle, so it costs no battery when nothing is happening

## 1.15.0 · 2026-10-31 · Per-game settings, panic key, clipboard

- Per-game settings (Settings > Game Center): each game gets its own performance mode, held notifications and no night light while it's open, and everything goes back when you close it
- Panic key (SUPER + CTRL + BACKSPACE): hides every window, pauses and mutes the sound and locks the screen; unlock and it all comes back where it was
- Volume and brightness changes show in the island instead of a separate pop-up (fullscreen games still get the pop-up)
- Clipboard page (Settings > Clipboard): search what you copied, copy it again, pin snippets you paste often, remove entries; Arabic text works

## 1.14.0 · 2026-10-31 · Pomodoro and a tidier Settings

- Pomodoro: set Rounds in Lennox Settings > Focus (say 4) and focus, break, focus, break repeat by themselves, with a long break at the end
- The island shows which round you're on (Focus 2/4), with Next round now and +5 min
- Lennox Settings is tidier: pages are in groups (Look & feel, Devices, Everyday, Keep it safe, Help)
- A search box in Settings finds pages by what you want to do ("arabic", "free space", "bluetooth", "pomodoro")
- The quick panel's volume now lists apps by name, with an Apps button to turn one down

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
