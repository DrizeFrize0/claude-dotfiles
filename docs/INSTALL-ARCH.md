# Installing Arch Linux for Lennox

This guide is written for an Intel laptop with an NVIDIA GTX 1650 (Acer / HP / Dell), but it works on most PCs. Budget about an hour. Have a phone with this page open, since your laptop won't have a browser for part of it.

> **Back up first.** Installing Arch the way described here **erases the whole drive**. If you want to keep Windows next to Arch (dual boot), read [Dual boot](#dual-boot-with-windows) first.

## 1. Make a USB stick

1. Download the latest ISO from <https://archlinux.org/download/>.
2. Write it to a USB stick (4 GB+): [Ventoy](https://www.ventoy.net/), [balenaEtcher](https://etcher.balena.io/) or [Rufus](https://rufus.ie/) (choose "DD image" mode in Rufus).

## 2. Laptop settings (BIOS / UEFI)

Restart and open the setup (usually `F2` on Acer/Dell, `F10` or `Esc` on HP):

- **Secure Boot: Disabled.** The NVIDIA driver is built on your machine and isn't signed, so it won't load with Secure Boot on.
- **Storage / SATA mode: AHCI** (not "RAID", "Intel RST" or "VMD"). If the Arch installer can't see your SSD, this is why. *If Windows is still on the disk, switching this can stop Windows from booting; that's fine if you're replacing Windows.*
- Boot from the USB stick (often `F12` for a boot menu).

## 3. Get online

Pick **Arch Linux install medium** at the boot menu. When you see a `root@archiso` prompt:

```sh
iwctl
# inside iwctl:
device list                      # usually "wlan0"
station wlan0 scan
station wlan0 get-networks
station wlan0 connect "Your Wi-Fi"
exit
ping -c 3 archlinux.org          # Ctrl+C if it keeps going; replies = online
```

A cable works too and needs no setup.

## 4. Run archinstall

```sh
archinstall
```

Go through the menu with the arrow keys and Enter. Use these answers:

| Option | Choose |
| --- | --- |
| Archinstall language, Locales | Your language and keyboard (e.g. `us`, `uk`, `de`) |
| Mirrors | Your country (faster downloads) |
| Disk configuration | *Use a best-effort default partition layout* → your SSD → **btrfs** → **Yes** to default subvolumes → **zstd** compression |
| Swap | **zram** (yes) |
| Bootloader | **GRUB** (this is what lets you pick an older snapshot at boot if an update ever breaks something) |
| Hostname | Anything, e.g. `lennox` |
| Root password | Set one (and remember it) |
| User account | Add your user, **Yes** to superuser (sudo) |
| Profile | **Minimal** (Lennox installs the whole desktop) |
| Audio | **Pipewire** |
| Kernels | `linux` |
| Network configuration | **Use NetworkManager** |
| Additional packages | `git` |
| Timezone | Yours |
| Automatic time sync (NTP) | Yes |

Pick **Install**, wait, choose **No** when asked to chroot, then:

```sh
reboot
```

Remove the USB stick when the screen goes black.

## 5. Install Lennox

> The step-by-step version of this part, with first-day setup and everyday tips, is in [AFTER-INSTALL.md](AFTER-INSTALL.md).

Log in with your user on the black text screen. Connect to Wi-Fi:

```sh
nmtui
```

(*Activate a connection* → your network → password → *Back* → *Quit*.)

Then:

```sh
git clone https://github.com/DrizeFrize0/claude-dotfiles.git ~/lennox
cd ~/lennox
./install.sh
```

> If the repository is private, GitHub asks for a username and a *token* instead of your password (github.com → Settings → Developer settings → Personal access tokens). Making the repo public avoids that.

The installer asks four yes/no questions, then works for 15 to 40 minutes (the NVIDIA driver is compiled for your kernel, which takes a few minutes). Enter your password when asked. When it says **Lennox is installed**, let it restart.

## 6. First login

On the login screen choose **Lennox (Hyprland)** (bottom-left session menu) and log in. Lennox Settings opens with a welcome page. Good first steps:

1. `SUPER + W`: pick a wallpaper; everything re-colors.
2. `SUPER + I` → **Health Check**: confirms graphics, sound, mic and touchpad drivers.
3. `SUPER + I` → **Sound** → *Test the microphone*.

## Dual boot with Windows

If you want to keep Windows:

1. In Windows, shrink the Windows partition (Disk Management → right-click C: → *Shrink Volume*) to free at least 80 GB.
2. In Windows, turn off *Fast Startup* (Control Panel → Power Options → *Choose what the power buttons do*) and BitLocker if it's on.
3. In archinstall's disk configuration choose **Manual partitioning**: keep the existing EFI partition (mount it at `/boot`, don't format it), and create one **btrfs** partition in the free space mounted at `/`.
4. After installing Lennox, run `sudo pacman -S os-prober`, add `GRUB_DISABLE_OS_PROBER=false` to `/etc/default/grub`, then `sudo grub-mkconfig -o /boot/grub/grub.cfg`. Windows then appears in the GRUB menu.

When in doubt, ask someone who has done it before, or install on the whole disk.
