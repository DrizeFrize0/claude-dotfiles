# Island and bar redesign: the brief

For a fresh session ("start the island redesign"). Decisions are made here so
the session only builds, tests and ships. Work in small versions.

## Dynamic island

Goal: cleaner, smoother, more alive, with real icons.

**Motion**
- Grow and shrink with a spring (`Adw.SpringAnimation` on the pill's width and
  height), not a jump. Content cross-fades (`Gtk.Stack`, crossfade) between
  what it shows instead of rebuilding widgets.
- New event: a small bounce. Alarm ringing: a gentle shake and a pulsing ring.
- Only run animation timers while something moves (idle = zero wake-ups).

**Look**
- Black pill, 1 px inner highlight, soft colored glow ring per activity
  (music = theme accent, timer = amber, focus = green, recording = red dot
  that pulses, call = blue).
- Album art with rounded corners and a thin progress ring around it.
- Timers and focus: a circular countdown ring instead of plain text.
- Long titles scroll slowly (marquee) instead of being cut.

**Two things at once** (the iPhone way): when two activities run (music +
timer), the pill splits into two linked blobs, one per side, each showing its
own icon and value.

**Icons**
- One consistent bundled icon set (SVG, symbolic, recolorable; Lucide or
  Phosphor, MIT/ISC) in `~/.config/lennox/assets/icons/island/`: music, play,
  pause, skip, timer, alarm, reminder, focus, break, call, mic, camera,
  charging, plug, battery, wifi, bluetooth, volume, brightness, notification,
  record, screenshot, panic, game, lock, check, close.
- Each activity has its icon and color; the settings page previews them.

**Gestures**
- Hover = open, click = pin, scroll on music = volume, middle click = skip,
  right click = a small menu (hide for an hour, settings).

**Tests to keep green:** `run_island.sh`, `run_island_big.sh`,
`run_widgets_interact.sh`, plus new checks for the split state and the
animations finishing at the right size.

## Waybar

Goal: richer, more decorated, still fast.

- **New themes:** "Aurora" (frosted glass with a gradient edge from the theme
  colors), "Pills" (chunky rounded modules with colored icon chips), "Minimal
  Dots" (tiny, quiet). Existing Islands / Line / Modern stay.
- **Workspaces:** the active one is an elongated pill that slides between
  dots (CSS transitions on min-width).
- **Icons:** every module gets a matching icon in a colored chip (Nerd Font
  glyphs, one size and baseline), tooltips restyled to match the bar.
- **Decor:** optional subtle noise texture, blurred backdrop with a hairline
  top highlight, hover glows, spacing and radius tokens shared by all themes,
  a per-theme "density" (compact / comfortable).
- **Limits (be honest in the UI):** Waybar's CSS is GTK3 CSS: transitions work,
  `@keyframes` do not. Motion comes from transitions and from module signals.
- Settings: Bar & Dock page gets a theme gallery with live previews.

## Order
1. Island motion + icons (biggest visible change)
2. Island two-activity split
3. Waybar Aurora + workspace pill
4. Waybar icon chips + Pills + Minimal Dots
5. Theme gallery page
