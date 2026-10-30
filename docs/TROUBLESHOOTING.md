# Troubleshooting

**Start here:** run `lennox doctor` in a terminal (or Lennox Settings → Health Check). It checks graphics, sound and microphone, touchpad, network, updates and the desktop, and prints the fix for each problem.

Logs:

| What | Where |
| --- | --- |
| Desktop start-up | `~/.local/state/lennox/autostart.log` |
| Installer | `~/.local/state/lennox/install.log` |
| Automatic updates | `/var/log/lennox-autoupdate.log` and `/var/lib/lennox/autoupdate-status.json` |
| Bar / dock | `$XDG_RUNTIME_DIR/lennox/waybar.log`, `dock.log` |
| Hyprland | `hyprctl configerrors`, or the red error bar at the top of the screen |

## An update broke something

1. **Roll back from the boot menu** (btrfs + GRUB installs): restart, pick **Arch Linux snapshots** in GRUB, then the snapshot from just before the update (`pre` snapshots are made automatically). Once the desktop works, open **Btrfs Assistant** (Lennox Settings → Updates → Manage snapshots) and *Restore* that snapshot to make it permanent.
2. No desktop at all? Press `CTRL + ALT + F3` for a text console, log in, then run `lennox doctor` or `sudo pacman -Syu` to finish a half-done update.

The automatic updater never restarts your computer and refuses to finish if the NVIDIA driver didn't rebuild, so it can't leave you with a broken graphics driver after a reboot.

## Black screen or no desktop after login

- Press `CTRL + ALT + F3`, log in, run `lennox doctor`.
- NVIDIA driver not built: `sudo dkms autoinstall`, then reboot.
- Start Hyprland by hand to see its error: `start-hyprland` (from the console).

## External monitor doesn't work

On many GTX 1650 laptops the HDMI port is wired to the NVIDIA GPU. Lennox Settings → Graphics → **Mode**: *Automatic* turns the NVIDIA GPU on at login when a screen is plugged in, so plug it in **before** logging in (or log out and back in). *Intel + NVIDIA* keeps it on all the time. Then arrange the screens in Lennox Settings → Display → *Arrange displays*.

## No sound, or the microphone / speakers sound bad

- `lennox sound check` (or Lennox Settings → Sound → *Drivers and sound quality*) shows which driver each sound chip uses, firmware or driver errors from startup, missing packages, and the usual causes of a bad mic. Every problem comes with its fix.
- `lennox sound fix` fixes the safe ones: a mic set above 100% (that only adds hiss), mic boost turned all the way up, a sound card switched off or left in Pro Audio mode. Then it restarts sound.
- **Clean microphone** (Lennox Settings → Sound, on by default): noise suppression, echo cancelling and steady volume, like Windows' mic enhancements. Apps record from *Microphone (clean)*. `lennox sound clean-mic off` turns it off.
- **Sound card switched off / no sound at all (not even headphones):** *Fix problems* turns the card back on; if it's stuck it also resets WirePlumber's saved sound settings (a backup is kept in `~/.local/state/wireplumber.lennox-backup`). If the card still won't start, the driver can't run it: Lennox Settings → Sound → **Sound driver** → *HDA* (older, simple: speakers, headphones and headset mic) or *SOF* (newer, needed for built-in digital mics), then restart. *Automatic* undoes it (`lennox sound driver auto`).
- **Bluetooth headphones sound bad in calls / the sound keeps switching:** a Bluetooth headset can only use its mic in "call mode", which sounds like an old phone line, and it shows up as a different output each time it flips. Lennox keeps Bluetooth headphones in full quality and you talk through the laptop mic (cleaned up by the clean microphone). Want the headset mic anyway? Lennox Settings → Sound → *Use the Bluetooth headset's mic*. *Fix problems* pulls a headset stuck in call mode back to full quality.
- **The sound jumps to HDMI by itself:** the NVIDIA HDMI output appears whenever the GPU wakes up. Lennox never picks HDMI by itself (`lennox sound outputs`); choose it in Settings → Sound when you plug in a TV.
- Still bad? `lennox sound report` saves everything about your sound to a text file (and copies it) so you can share it.
- Most Intel laptop microphones need `sof-firmware` (Lennox installs it). After installing it, restart.
- Lennox Settings → Sound: pick the right output / microphone and use *Test the microphone*.
- Is the mic muted? The mic key toggles it, and the quick panel (`SUPER + N`) has a Microphone tile.

## Touchpad not working

- `hyprctl devices` should list a touchpad. If not: `sudo dmesg | grep -i -E "i2c|touchpad|elan|synaptics"`.
- Some laptops have a touchpad-off key: press it again (or run `lennox-touchpad on`).
- Settings: Lennox Settings → Keyboard & Touchpad.

## Bar is missing or looks wrong

`SUPER + SHIFT + B` restarts it. Clicking workspace numbers in the bar uses Lennox's own workspace buttons (the built-in Waybar module can't switch workspaces with Hyprland's new Lua config yet). If they show only 1 to 5 and never update, check that `lennox-workspaces` is running: `pgrep -af lennox-workspaces`.

## Widgets or dashboard missing

- `SUPER + D` does nothing: run `lennox doctor`. It checks that `gtk4-layer-shell` is installed and the widgets are running. Start them by hand with `setsid -f lennox-widgets`.
- Desktop widgets hidden: `SUPER + CTRL + W`, or Lennox Settings → Widgets.
- Weather says it can't find your city: try the nearest bigger city, or add the country ("Springfield, US"). "Daily API request limit" means the free weather service is busy; it retries by itself.

## Reset things

| Reset | How |
| --- | --- |
| All Lennox settings | `rm ~/.config/lennox/settings.json && lennox-apply all` |
| Your Hyprland tweaks | `mv ~/.config/hypr/custom.lua ~/custom.lua.bak` |
| Get old configs back | they're in `~/.local/share/lennox/backups/<date>/` |
| Re-install Lennox files | `cd ~/lennox && ./install.sh --update` |

## Games

- Steam (Proton) games pick the GTX 1650 automatically.
- Native Linux / OpenGL games: add `prime-run %command%` to the game's Steam launch options.
- Minecraft (Prism Launcher) is already set to use the GTX.
- Any other app: `prime-run app` or `lennox gpu run app`.
- `SUPER + ALT + G` (game mode) turns off effects and switches to the performance power mode.

## Phone not found (KDE Connect)

- Both on the same Wi-Fi, and the KDE Connect app open on the phone.
- Guest or school / work Wi-Fi often blocks devices from seeing each other: try your home Wi-Fi or a phone hotspot.
- Restart the PC side: `pkill kdeconnectd; /usr/lib/kdeconnectd &` then press the refresh button in `SUPER + I` → **Phone**.
- `lennox phone status` shows what KDE Connect sees.

## App Store or Cleanup

- An install failed: the small window shows why. Running `lennox update` first fixes most "not found" errors.
- `lennox cleanup` lists what can be freed; `lennox cleanup now` cleans from a terminal.

## Focus mode

- A blocked site still loads: the browser may remember it for a minute, or use "secure DNS" (DNS over HTTPS), which skips the block. Zen / Firefox: Settings → Privacy & Security → DNS over HTTPS → Off.
- Sites stay blocked after a crash: `lennox focus stop` (or log out and in) unblocks them.
- `lennox focus status` shows the session; `lennox focus stats` your totals.
