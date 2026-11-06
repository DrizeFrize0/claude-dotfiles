# What's new in Lennox

Newest first. After `lennox upgrade` you get a notification with the
highlights, and Lennox Settings > About lists everything.

## 1.34.2 · 2026-11-06 · IPv6 off really works, and the packet size is judged correctly

- Fixed: turning IPv6 off was refused by NetworkManager when IPv6 DNS servers were set on the connection (the fast DNS step sets them). lennox-net now clears them in the same step, applies the change right away, and shows the real error if it still fails
- Fixed: after the packet size was set (for example 1492), lennox-net check kept complaining, because it tested with full-size packets. It now tests with the size the connection is set to, so a connection that was fixed shows as fine
- The fast DNS no longer fails on a connection that has IPv6 turned off (it only sets the IPv4 servers there)

## 1.34.1 · 2026-11-06 · lennox-net finds your connections, and fixes the packet size

- Fixed: lennox-net didn't find any wired or Wi-Fi connection on newer NetworkManager (it calls them ethernet and wifi), so "IPv6 off" and the fast DNS changed nothing. Both work now, and the upgrade sets the fast DNS again
- New: when big packets don't get through (a connection that can only carry smaller packets than normal, which makes some sites hang halfway or load only partly), lennox-net measures the biggest size that works and fix --yes sets exactly that on your connections
- lennox-net says plainly when there was no active connection to change

## 1.34.0 · 2026-11-06 · Fast DNS, a fix for blocked sites, and a spinner

- lennox-net: finds out why sites don't open (on a cable or on Wi-Fi) and fixes it. It tests the cable (speed and duplex), the DNS, IPv6, packet size, a handful of sites and proxies, and says in plain words what is wrong. lennox-net fix --yes does the safe fixes: removes a leftover site block, switches to a fast DNS, turns off IPv6 where it is set up but broken. Settings > Wi-Fi & Bluetooth > Internet, cable and DNS has the same two buttons
- Found while looking: Lennox's own focus mode blocks YouTube, TikTok, Instagram, Reddit, X and Twitch by adding them to /etc/hosts, and if a session ended badly that block stayed behind, on any connection. lennox-net now finds that and takes it out (never during a running focus session)
- A fast DNS for the whole laptop: Lennox measures Cloudflare, Google, Quad9 (and your router) from your own network and uses the quickest for every wired and Wi-Fi connection. The upgrade does this once; Settings > DNS changes or undoes it (Automatic = what the network hands out). lennox-net dns bench shows the numbers
- A spinner in the terminal for the slow steps of lennox upgrade (installing packages, building AUR packages, finding the fastest DNS), with the time it has taken. The command's own output goes to the log; if it fails, its last lines are shown

## 1.33.1 · 2026-11-06 · A nicer lennox upgrade

- lennox upgrade (and the installer) look better in the terminal: a boxed header with the old and new version, the list of what changed, numbered-style steps with a diamond, green checks, yellow triangles for things to look at, how long each slow step took, and a closing box with the total time. Colors only appear in a real terminal (never in the log file or when piped), and NO_COLOR turns them off
- The "what's new" part now comes right before the closing box, so the last thing you see is whether everything went well

## 1.33.0 · 2026-11-06 · Simple sound

- Simple sound (Settings > Sound > Keep it simple, or lennox-sound simplify on): only your laptop and your Bluetooth headphones are offered. The graphics chip's HDMI/DisplayPort audio, the HDMI outputs of the main chip and the headset jack's microphone are hidden, so the long list of sound sources shrinks to what you use. lennox-sound simplify status shows exactly what is offered, and lennox-sound simplify off brings everything back. The upgrade turns it on once
- Calls on Discord sound natural again: the extra "clean" microphone is turned off. Discord cleans your voice itself, and two cleaners on top of each other make it sound robotic and bad. You can still turn it on in Settings > Sound
- Laptop microphone or the Bluetooth headset's microphone: your choice in Settings > Sound > Use the Bluetooth headset's mic (off: headphones in full quality and you talk through the laptop mic; on: the headset mic works but calls sound like a phone line)

## 1.32.0 · 2026-11-06 · The power mode follows the charger, and tells you

- The power mode now picks itself: Performance when plugged in, Balanced on battery at 80% or more, Power saver on battery below 80%. All of it (the three modes and the 80%) is in Settings > Power & Battery > Power mode by itself, and it can be turned off
- You get a message every time the power mode changes, whoever changed it: the new mode and why (plugged in, on battery at 62%, changed by you or another program). The bar's power item also shows the reason when you hover it
- A power mode you pick by hand stays until something real changes (you plug in, unplug, or the battery crosses 80%). Game mode is left alone and the rule catches up when it ends. It does not flip back and forth around 80%

## 1.31.2 · 2026-11-05 · No more false heat alarms

- Heat alerts now wait for 2 minutes of real heat in a row, and the processor limit is 95 degrees. A short spike to 98 that drops back to 50 a moment later (the processor racing for a second when something starts) is normal and no longer raises an alarm or switches to Quiet mode. The upgrade moves your old limit of 92 to 95
- New fan profile "Cool" (Settings > Extras > Fan and noise): holds the processor to 80%, which trims those short spikes and costs almost nothing you can feel. The upgrade picks it for you if you were on Normal
- New: lennox-heat watch records the temperature and the busiest program every second for a minute and tells you what causes the spikes, and whether they are short boosts or lasting heat

## 1.31.1 · 2026-11-04 · The screensaver and pet no longer heat the laptop

- Found with lennox-heat: a screensaver left running and the desktop pet were using a lot of processor time and heating the laptop. The screensaver now draws far less (stars and aurora use a fraction of the work, and the calm scenes run at 12 to 20 pictures a second), ends when the lock screen appears or when you come back, never runs longer than 12 minutes, and can only run once. The pet no longer starts a program on every frame, and cursor effects slow down to a trickle while the mouse is still
- lennox-heat now names which Lennox part is using the processor, and lennox-heat cool also stops a screensaver that is still running

## 1.31.0 · 2026-11-04 · Why is it hot?

- New tool: lennox-heat. It shows the processor temperature and speed, what is using the processor most, the power settings, the fans, and whether Lennox extras, a live wallpaper, game mode or the NVIDIA chip could be adding heat, and tells you what to do about each. lennox-heat cool applies the safe steps right away (Quiet power mode, game mode off, extras off, turbo off) and shows the temperature drop. If nothing in the software explains it, it says so and lists the hardware causes (dust, thermal paste, blocked vents, BIOS fan setting)
- The heat alert now switches to Quiet mode by itself when the processor is too hot and you are not gaming (a switch in Settings > Daily care turns this off). While gaming you still get the button instead

## 1.30.5 · 2026-11-04 · Where does Horizon keep Minecraft?

- lennox-mods horizon works out which folder Horizon uses for Minecraft. It checks a running game's own command line (the surest sign), what Horizon's settings files say about folders, and the folders Horizon created, and says what to do if it simply uses the standard .minecraft folder

## 1.30.4 · 2026-11-04 · lennox-mods shows empty folders and skips LabyMod's own files

- lennox-mods find now also lists mods folders that are empty (a new launcher's folder is empty until you add mods) and looks inside Horizon's data folders
- lennox-mods copy skips LabyMod's own files (they only work inside LabyMod) and explains when you type the placeholder words instead of real paths

## 1.30.3 · 2026-11-04 · lennox-mods finds the folders for you

- lennox-mods find now lists every folder named mods or addons that has files in it, anywhere in your home folder, plus where Horizon is installed (Flatpak, package, or any folder or file with its name). You no longer need to know where LabyMod or Horizon keep their files

## 1.30.2 · 2026-11-04 · Find and copy Minecraft mods

- New tool: lennox-mods. lennox-mods find shows where LabyMod and your launchers (like Horizon) keep their mods and how many each has, and lennox-mods copy FROM TO copies the mods across. It only copies (never moves or deletes), skips mods that are already there, and shows what it would do until you add --yes

## 1.30.1 · 2026-11-04 · The Night logo

- The Lennox logo is now Night 4: a warm full moon on a deep navy tile with a bold L cut out of it and a few stars. It is used in the boot menu (above the entries and as the Arch Linux icon) and in the welcome animation at login. After upgrading, run lennox-bootmenu restyle to update the boot menu

## 1.30.0 · 2026-11-04 · The Lennox logo

- A Lennox logo: a rounded tile with a glowing blue-to-violet gradient, a bold L and a small spark. It lives in ~/.config/lennox/assets/logo (a scalable SVG and 128, 256 and 512 pixel pictures)
- The boot menu shows it above the entries and as the icon of the Arch Linux entry (run lennox-bootmenu restyle), and the welcome animation at login shows it above your name
- Fixed: the boot menu showed every entry several times. Each restyle added the same include line to the menu's settings again, because the file can only be read by the administrator and the check could not see it. The line is now removed and added exactly once, so running restyle again repairs a menu that is already doubled

## 1.29.5 · 2026-11-04 · Boot menu picture on ImageMagick 7

- lennox-bootmenu restyle works with ImageMagick 7 (it uses magick when it exists), finds a font file by itself so the LENNOX name is drawn on the boot menu background, and no longer prints the deprecation warnings

## 1.29.4 · 2026-11-04 · Exactly two entries

- The boot menu now has two fixed entries, Arch Linux and Windows, and no automatic scanning, so boot files on your other disk partitions (old installs) can no longer show up as extra Linux entries. Windows is found from the laptop's own boot list; if it can't be found, the menu keeps scanning so Windows still shows. After upgrading, run lennox-bootmenu restyle

## 1.29.3 · 2026-11-04 · Boot options in every place

- The startup animation also edits a kernel options file that the mkinitcpio preset names with --cmdline (the build reads only that file when it is named), and puts the original back on disable. With this, quiet and splash reach the boot file whichever place your Arch reads its options from

## 1.29.2 · 2026-11-04 · No boot messages

- The startup animation now checks the real boot file instead of just the settings files: the quiet and splash options must be inside the rebuilt file, and if they are not it tells you. That was why boot messages still showed even though the animation was installed. The options also go into every place Arch reads them from (both cmdline.d and /etc/kernel/cmdline), plus a quieter console (loglevel=3, no udev noise, no blinking cursor)
- lennox-boot-animation status shows the options inside your boot file next to the ones running now
- To fix an existing setup: lennox-boot-animation enable --yes again, then restart

## 1.29.1 · 2026-11-04 · Boot menu: no doubles

- The boot menu showed Arch twice and the power, restart and firmware buttons twice. Now there is one Arch Linux, one Windows and one row of buttons. After upgrading, run lennox-bootmenu restyle

## 1.29.0 · 2026-11-04 · A nicer boot menu and a welcome

- The boot menu is cleaner and prettier: a night-sky background, a glowing selection, and only Arch Linux and Windows (the extra Linux entries are hidden). After upgrading, run lennox-bootmenu restyle to apply it
- Welcome animation: a few seconds of stars and "Good evening, YOUR NAME" every time the desktop starts. Any key skips it. Settings > Daily care > Greeting turns it off
- The startup animation (lennox-boot-animation) now works with your kind of setup, where Arch starts from one boot file built by mkinitcpio. It puts the splash option into the kernel options file instead of a boot loader file, and still shows its plan first and keeps backups
- New tool: lennox-sessions hide-others makes the login screen list only "Lennox (Hyprland)" (lennox-sessions show-all undoes it). Use the Lennox entry: it picks the right graphics chip and starts everything, the plain Hyprland entry does not

## 1.28.4 · 2026-11-04 · Clean up old boot entries

- lennox-bootmenu clean lists the boot entries that point to partitions that no longer exist (left over from old installs), and lennox-bootmenu clean --yes removes them after saving a backup. Windows, the boot menu, USB drives and the laptop's own entries are never touched, and nothing is removed if the partitions can't be read

## 1.28.3 · 2026-11-04 · The boot menu status is right

- lennox-bootmenu status now finds the boot partition and sees rEFInd on it even though only the administrator may open /boot (it said "not found" and "not installed" although the menu was installed)

## 1.28.2 · 2026-11-04 · The boot menu can read /boot

- lennox-bootmenu now reads the boot partition with sudo. On Arch that partition can only be read by the administrator, so as a normal user the tool saw an empty folder and said there was no Arch boot file. It also ignores GRUB's own files and prefers the files in EFI/Linux

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
