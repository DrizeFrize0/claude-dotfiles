# After installing Arch: the full Lennox tutorial

You just finished `archinstall`, typed `reboot`, and pulled out the USB stick. This guide takes you from the black text screen to a finished Lennox desktop, then shows you how to use it day to day.

**Keep this open on your phone.** Until Lennox is installed, your laptop has no browser.

Time needed: about 45 minutes, mostly waiting.

---

## Part 1: First boot (text screen)

### 1.1 Log in

You'll see something like:

```
lennox login: _
```

Type **your username** (the user you made in archinstall, not `root`) and press Enter, then type your password. **Nothing shows up while you type the password.** That's normal, so just type it and press Enter.

You're in when you see a prompt like `[you@lennox ~]$`.

### 1.2 Connect to Wi-Fi

```sh
nmtui
```

1. Pick **Activate a connection** (arrow keys + Enter).
2. Pick your Wi-Fi, type the password, press Enter.
3. A `*` appears next to it when it's connected. Pick **Back**, then **Quit**.

Check you're online:

```sh
ping -c 3 archlinux.org
```

Three lines with `time=` mean you're online. `Temporary failure in name resolution` means you aren't: run `nmtui` again.

> **Using a cable?** Just plug it in. No setup needed.

### 1.3 Update the system first

```sh
sudo pacman -Syu
```

Type your password and press `Y` + Enter when it asks. This avoids problems with old packages from the USB stick.

> **Seen `error: failed to synchronize all databases`?** Run `sudo pacman -Syu` once more. The mirrors are sometimes busy.

---

## Part 2: Install Lennox

### 2.1 Download Lennox

```sh
sudo pacman -S --needed git
git clone -b claude/lennox-arch-dotfiles-izl6m6 https://github.com/DrizeFrize0/claude-dotfiles.git ~/lennox
```

> Once the Lennox branch is merged into `main` on GitHub, you can drop the `-b claude/lennox-arch-dotfiles-izl6m6` part.
>
> **Asked for a username and password?** The repository is private. Either make it public on GitHub (Settings → General → Danger Zone → Change visibility), or use a GitHub *token* as the password (github.com → Settings → Developer settings → Personal access tokens → Generate new token, with `repo` access).

### 2.2 Run the installer

```sh
cd ~/lennox
./install.sh
```

**Don't** use `sudo` here. The installer asks for your password itself when it needs it.

It asks four questions. Press Enter to say yes, or type `n` + Enter for no:

| Question | What it adds |
| --- | --- |
| Gaming | Steam, Prism Launcher (Minecraft), GameMode, MangoHud |
| Discord | Vesktop (Discord with working screen share) |
| Server dev tools | VS Code, IntelliJ, Java 21, Maven, Gradle, SFTP. Handy for AstralNetwork plugins |
| AUR extras | Bibata cursor and the Oh My Posh prompt |

Then it works on its own for **15 to 40 minutes**. The NVIDIA driver is built for your laptop during this, so the screen can look stuck for a few minutes. It isn't. Leave the laptop **plugged in** and don't close the lid.

It may ask for your password again partway through. That's normal.

### 2.3 Restart

When it prints **Lennox is installed**, answer **yes** to *Restart now?*

Read anything printed in yellow with a `!` first. Those are warnings, things that didn't fully work. Take a photo of them with your phone in case you need them later.

> **The installer stopped with a red ✗?** Run `./install.sh` again. It's safe to repeat and continues where it stopped. If it fails at the same spot, the full log is at `~/.local/state/lennox/install.log`. Show it to Claude.

---

## Part 3: First login

### 3.1 The login screen

You'll see the ML4W login screen with a wallpaper.

1. Check the session menu (bottom-left) says **Lennox (Hyprland)**. Pick it if it doesn't.
2. Type your password and press Enter.

Lennox Settings opens with a **Welcome** page.

### 3.2 The five-minute setup

Do these in order. `SUPER` is the Windows key.

1. **Pick a wallpaper:** `SUPER + W`. Click one and the whole desktop (bar, menus, terminal, lock screen) re-colors to match it.
2. **Run the health check:** `SUPER + I` → **Health Check**. Everything should be green. If something isn't, it tells you how to fix it.
3. **Test sound:** play anything, or use the volume keys. You should hear it and see a volume pop-up.
4. **Test the mic:** `SUPER + I` → **Sound** → *Test the microphone*. Speak, then listen back.
5. **Test the touchpad:** two-finger scroll, tap to click, and swipe left/right with **three fingers** to switch workspaces.
6. **Meet the bar:** click the ✦ star for your apps (right-click it for the dashboard), click the clock for the dashboard. `SUPER + CTRL + T` switches between Lennox Islands and Lennox Line (the classic ML4W bars are there too).
7. **Turn on the weather:** `SUPER + I` → **Widgets** → type your city → ✓. The clock, weather and music now show on your wallpaper.
8. **Try a look:** `SUPER + I` → **Appearance** → Looks: *Lennox*, *Glass*, *Neon* (spinning border), *Minimal*… one click each.

### 3.3 Sign in to your stuff

- **Browser:** `SUPER + B` opens Zen. Sign in to your accounts or import bookmarks.
- **Discord:** `SUPER + SPACE`, type `vesktop`, Enter.
- **Steam:** `SUPER + SPACE`, type `steam`. The first start downloads an update.
- **Minecraft:** `SUPER + SPACE`, type `prism`. Add your Microsoft account in Prism Launcher. It already runs on the GTX 1650.

---

## Part 4: Using Lennox every day

### 4.1 The keys worth learning

| Keys | What it does |
| --- | --- |
| `SUPER + SPACE` | Open any app (just start typing) |
| `SUPER + RETURN` | Terminal |
| `SUPER + B` | Browser |
| `SUPER + E` | Files |
| `SUPER + Q` | Close a window |
| `SUPER + F` | Fullscreen |
| `SUPER + T` | Make a window float (or tile it again) |
| `SUPER + arrows` | Move between windows |
| `SUPER + 1 … 0` | Go to workspace 1 to 10 |
| `SUPER + SHIFT + 1 … 0` | Move the window to that workspace |
| `SUPER + V` | Clipboard history |
| `PRINT` | Screenshot an area (saved and copied) |
| `SUPER + L` | Lock |
| `SUPER + ESC` | Power menu (lock, sleep, restart, shut down) |
| `SUPER + I` | Lennox Settings |
| `SUPER + N` | Quick panel |
| `SUPER + D` | Dashboard |
| `SUPER + CTRL + K` | **Forgot a key? Search all of them here** |

Full list: [KEYBINDINGS.md](KEYBINDINGS.md).

### 4.2 How windows work

Hyprland is a *tiling* desktop. New windows split the screen instead of stacking on top of each other:

- One window fills the screen. Open a second and they share it side by side.
- Want an old-style floating window? `SUPER + T`, then drag it with `SUPER + left mouse` and resize with `SUPER + right mouse`.
- Running out of space? Use another workspace (`SUPER + 2`, `SUPER + 3`…), like having several desktops.

A layout that works: workspace 1 for the browser, 2 for code, 3 for Discord, 4 for games.

### 4.3 The quick panel (`SUPER + N`)

Phone-style controls in one place:

- Tiles: Wi-Fi, Bluetooth, microphone, night light, **game mode**, stay awake, battery saver, dark mode
- Sliders: volume, mic and brightness
- Music controls and your notifications

### 4.4 The dashboard (`SUPER + D`)

Slides in from the left:

- Your name, how long the laptop has been on, and buttons for Settings, Lock and Power
- **Quick actions:** screenshot, color picker, wallpaper, shuffle wallpaper, night light, game mode, dark/light, clipboard
- Volume and brightness sliders, the music that's playing, the weather with 3 days ahead, a calendar, system stats
- **Notes:** type anything (gym times, server ideas, homework); it saves by itself

Press `Escape`, `SUPER + D` again, or click next to it to close it.

### 4.5 Lennox Settings (`SUPER + I`)

Everything is here. You never need to edit a config file:

| Page | Use it for |
| --- | --- |
| Appearance | Dark/light, gaps, rounded corners, blur, animations, fonts |
| Wallpaper | Pick, shuffle, or choose your wallpaper folder |
| Bar & Dock | Bar style, what it shows, dock on/off |
| Widgets | Desktop widgets (clock, weather, music, system), your city, the dashboard |
| Sound | Speakers/headphones, microphone, mic test |
| Display | Brightness, scale, refresh rate, arranging a second monitor |
| Keyboard & Touchpad | Layout, scroll direction, tap to click, speed |
| Wi-Fi & Bluetooth | Networks and Bluetooth devices |
| Power & Battery | Battery mode, sleep times, lid behaviour |
| Night | Night light (warm screen at night) and the wind-down reminder |
| Graphics | NVIDIA mode (Automatic / Intel only / Intel + NVIDIA) |
| Default Apps | Default browser, terminal, file manager |
| Updates | Auto-updates on/off, update now, snapshots |
| Keybindings | See every shortcut |
| Health Check | Finds and explains driver or system problems |

### 4.6 Gaming

- **Steam games** use the GTX 1650 automatically.
- For a native Linux game that runs slowly, open Steam → right-click the game → Properties → Launch options and type `prime-run %command%`.
- **Game mode:** `SUPER + ALT + G` (or the quick panel tile) turns off animations and blur and switches to performance mode. Turn it off afterwards to save battery.
- Plug in the charger for gaming. The GTX draws a lot of power.

### 4.7 A second monitor

1. Plug the monitor in **before** logging in (or log out and in again).
2. `SUPER + I` → **Display** → *Arrange displays* to place it left/right and set its resolution.

If it stays black, go to `SUPER + I` → **Graphics** → Mode and pick **Intel + NVIDIA**, then log out and back in. On many GTX laptops the HDMI port is wired to the NVIDIA card.

---

## Part 5: Updates and staying safe

### 5.1 You don't need to do anything

Lennox updates the system, drivers and Flatpak apps **by itself**, but only when:

- the laptop is on the charger,
- you're not on a phone hotspot,
- Arch hasn't announced that an update needs a manual step.

Before each update it takes a **snapshot** (a restore point). After it, it checks the NVIDIA driver was rebuilt properly. It never restarts your laptop for you.

**AUR apps** (a few extras like the cursor theme) don't auto-update. You get a notification instead: click it, or run `lennox update`.

### 5.2 Updating by hand

```sh
lennox update      # system, drivers, AUR apps, Flatpaks
lennox upgrade     # Lennox itself (new features and fixes)
```

### 5.3 If an update breaks something

1. Restart. In the GRUB menu (the list you see while booting), pick **Arch Linux snapshots**.
2. Pick the newest snapshot marked **pre** (made just before the update).
3. Once the desktop works, `SUPER + I` → **Updates** → *Manage snapshots* → restore that snapshot to make it permanent.

### 5.4 Updates paused by Arch news

Sometimes you'll get a notification that updates are paused because of Arch news. Read it (`SUPER + I` → **Updates**). Most news doesn't affect you. Once you've read it, press **Continue** under *Done reading?* and updates carry on.

---

## Part 6: Make it yours

Your own tweaks go in these files. Lennox never overwrites them:

| File | For |
| --- | --- |
| `~/.config/hypr/custom.lua` | Your own keybinds and Hyprland settings |
| `~/.config/zshrc/90-custom` | Your own terminal aliases |
| `~/.config/kitty/custom.conf` | Terminal font size and more |

Example: open Firefox with `SUPER + B` instead of Zen. Add this to `custom.lua`:

```lua
hl.unbind("SUPER + B")
hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { description = "Open Firefox" })
```

Then press `SUPER + SHIFT + R` to reload.

Quick looks from a terminal: `lennox look` lists them, `lennox look neon` applies one.

Your picture in the dashboard: save a square photo as `~/.face`.

Add your own wallpapers by dropping pictures into `~/.config/lennox/wallpapers` (or pick a different folder in Settings → Wallpaper).

---

## Part 7: If something goes wrong

**Always start with:**

```sh
lennox doctor
```

It checks graphics, sound, mic, touchpad, network and updates, and prints the fix for each problem.

| Problem | Try |
| --- | --- |
| Bar disappeared or looks broken | `SUPER + SHIFT + B` |
| Everything looks weird after a change | `SUPER + SHIFT + R` (reload Hyprland) |
| An app froze | `SUPER + SHIFT + Q` (force quit) |
| No sound | `SUPER + I` → Sound → check the right output is picked |
| Mic not working | Quick panel → is the Microphone tile off? Then Sound → mic test |
| Touchpad stopped | Press the touchpad key again, or run `lennox-touchpad on` |
| Wi-Fi gone | `SUPER + I` → Wi-Fi & Bluetooth, or run `nmtui` |
| Black screen after login | `CTRL + ALT + F3` → log in → `lennox doctor` |
| Everything broken after an update | Roll back from the boot menu (Part 5.3) |

More fixes: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Still stuck?** Take a photo of the screen or copy the output of `lennox doctor` and ask Claude. Mention what you were doing when it happened.

---

## You're done 🎉

Checklist:

- [ ] Logged in to **Lennox (Hyprland)**
- [ ] Picked a wallpaper (`SUPER + W`)
- [ ] Health Check all green (`SUPER + I`)
- [ ] Sound, mic and touchpad tested
- [ ] Browser, Discord, Steam signed in
- [ ] Learned `SUPER + SPACE`, `SUPER + Q`, `SUPER + I` and `SUPER + CTRL + K`

Enjoy it.
