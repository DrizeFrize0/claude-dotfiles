# Keybindings

`SUPER` is the Windows key. Press `SUPER + CTRL + K` on the desktop for a searchable list.
To change one, add to `~/.config/hypr/custom.lua`:

```lua
hl.unbind("SUPER + B")
hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { description = "Open Firefox" })
```

## Apps

| Keys | Action |
| --- | --- |
| `SUPER + RETURN` | Terminal (kitty) |
| `SUPER + B` | Browser (Zen) |
| `SUPER + E` | Files (Nautilus) |
| `SUPER + C` | Calculator |
| `SUPER + SPACE` / `SUPER + CTRL + RETURN` | App launcher |
| `SUPER + TAB` | Switch to an open window |
| `SUPER + V` | Clipboard history |
| `SUPER + CTRL + E` | Emoji picker |
| `SUPER + CTRL + K` | All keybindings |

## Lennox

| Keys | Action |
| --- | --- |
| `SUPER + I` | Lennox Settings |
| `SUPER + N` / `SUPER + CTRL + S` | Quick panel (toggles, sliders, notifications) |
| `SUPER + D` | Dashboard (actions, music, weather, calendar, notes) |
| `SUPER + CTRL + W` | Show / hide the desktop widgets |
| `SUPER + SHIFT + C` | Pick a color on screen (hex code copied) |
| `SUPER + W` | Wallpaper picker |
| `SUPER + SHIFT + W` | Random wallpaper |
| `SUPER + CTRL + T` | Bar style (Modern / Glass / Minimal) |
| `SUPER + SHIFT + M` | Dark / light mode |
| `SUPER + SHIFT + H` | Night light on / off |
| `SUPER + ALT + G` | Game mode on / off |
| `SUPER + CTRL + B` | Show / hide the bar |
| `SUPER + SHIFT + B` | Reload the bar |
| `SUPER + CTRL + D` | Show / hide the dock |
| `SUPER + SHIFT + R` | Reload Hyprland |

## Session

| Keys | Action |
| --- | --- |
| `SUPER + L` / `SUPER + CTRL + L` | Lock |
| `SUPER + ESC` / `SUPER + CTRL + P` | Power menu |

## Screenshots

Every screenshot is copied to the clipboard and saved in `~/Pictures/Screenshots`. Click **Edit** on the notification to draw on it.

| Keys | Action |
| --- | --- |
| `PRINT` / `SUPER + ALT + S` | Select an area |
| `SUPER + ALT + W` | Active window |
| `SUPER + ALT + F` | Whole screen |
| `SUPER + PRINT` | Screenshot menu (with timer) |

## Windows

| Keys | Action |
| --- | --- |
| `SUPER + Q` | Close |
| `SUPER + SHIFT + Q` | Force quit |
| `SUPER + F` | Fullscreen |
| `SUPER + M` | Maximize |
| `SUPER + T` | Float / tile |
| `SUPER + ALT + T` | Float and pin on every workspace |
| `SUPER + P` | Pseudo-tile |
| `SUPER + J` | Flip the split direction |
| `SUPER + K` | Swap the two halves |
| `SUPER + G` | Group windows into tabs |
| `SUPER + arrows` | Move focus |
| `SUPER + CTRL + arrows` | Move the window |
| `SUPER + ALT + arrows` | Swap with a neighbour |
| `SUPER + SHIFT + arrows` | Resize |
| `SUPER + left mouse` | Drag a window |
| `SUPER + right mouse` | Resize with the mouse |
| `ALT + TAB` | Cycle windows on this workspace |

If you set the main key to `ALT` (Lennox Settings → Keyboard), `SUPER` takes ALT's place inside shortcuts: `SUPER + ALT + G` becomes `ALT + SUPER + G`, and `ALT + TAB` becomes `SUPER + TAB`.

## Workspaces

| Keys | Action |
| --- | --- |
| `SUPER + 1 … 0` | Go to workspace 1 to 10 |
| `SUPER + SHIFT + 1 … 0` | Move the window there |
| `SUPER + CTRL + SHIFT + 1 … 0` | Send the window there, stay here |
| `SUPER + mouse wheel` | Next / previous workspace |
| `SUPER + S` | Show / hide the scratchpad |
| `SUPER + SHIFT + S` | Move the window to the scratchpad |

On AZERTY keyboards (`fr`, `be`) the number row keys work without Shift.

## Touchpad

| Gesture | Action |
| --- | --- |
| 3 fingers left / right | Switch workspace |
| 3 fingers up | Scratchpad |
| 4 fingers pinch out / in | Fullscreen on / off |

## Laptop keys

Volume, mute, mic mute, screen brightness, keyboard backlight, touchpad on/off, media play/pause/next/previous and the calculator key all work, including on the lock screen.
