"""Readable terminal colors for any wallpaper.

matugen takes the terminal's red, green, blue... straight from wallpaper
pixels, so a dark wallpaper (a night sky) gives a dark green that vanishes
on the dark background: zsh colors a finished command green and the text
"disappears". This builds the 16 terminal colors from real hues instead,
nudged toward the theme color so they still match, each one lightened (or
darkened in light mode) until it is easy to read on the background.

    python3 -m lennox.terminal_colors KITTY_COLORS_FILE [COLORS_JSON]
"""

import colorsys
import json
import os
import re
import sys

from . import settings as S

# Hues in degrees: red, green, yellow, blue, magenta, cyan
HUES = {1: 355, 2: 135, 3: 45, 4: 215, 5: 300, 6: 185}
NORMAL_CONTRAST = 4.5    # WCAG AA for text
BRIGHT_CONTRAST = 6.5
DIM_CONTRAST = 3.0       # color 8: comments, zsh suggestions (dim but visible)
WHITE_CONTRAST = 9.0


def hex_to_rgb(value):
    value = value.lstrip("#")[:6]
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def luminance(rgb):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def harmonize(hue, toward, amount=0.12):
    """Turn `hue` a little toward the theme hue (shortest way round)."""
    diff = (toward - hue + 180) % 360 - 180
    return (hue + diff * amount) % 360


def readable(hue, sat, bg, target, dark):
    """The color of this hue closest to the middle that reaches `target` contrast on bg."""
    steps = [i / 400 for i in range(200, 401)] if dark else [i / 400 for i in range(200, -1, -1)]
    for light in steps:
        # Check the color as it will be written (rounded to #rrggbb)
        rgb = hex_to_rgb(rgb_to_hex(colorsys.hls_to_rgb(hue / 360, light, sat)))
        if contrast(rgb, bg) >= target:
            return rgb
    return (1.0, 1.0, 1.0) if dark else (0.0, 0.0, 0.0)


def palette(bg_hex, primary_hex, dark=True):
    """Colors 0-15 as hex strings."""
    bg = hex_to_rgb(bg_hex)
    p_hue, _p_light, p_sat = colorsys.rgb_to_hls(*hex_to_rgb(primary_hex))
    p_hue *= 360
    out = {}
    for index, hue in HUES.items():
        h = harmonize(hue, p_hue)
        out[index] = rgb_to_hex(readable(h, 0.70, bg, NORMAL_CONTRAST, dark))
        out[index + 8] = rgb_to_hex(readable(h, 0.75, bg, BRIGHT_CONTRAST, dark))
    gray_sat = min(0.12, p_sat)
    out[0] = rgb_to_hex(colorsys.hls_to_rgb(p_hue / 360, 0.18 if dark else 0.85, gray_sat))
    out[8] = rgb_to_hex(readable(p_hue, gray_sat, bg, DIM_CONTRAST, dark))
    out[7] = rgb_to_hex(readable(p_hue, gray_sat, bg, WHITE_CONTRAST, dark))
    out[15] = rgb_to_hex(readable(p_hue, gray_sat * 0.5, bg, 12.0, dark))
    return out


def rewrite(kitty_file, colors_json=None):
    """Replace the colorN lines (and add missing ones) in a kitty colors file."""
    colors_json = colors_json or os.path.join(S.CONFIG_DIR, "colors.json")
    with open(colors_json, encoding="utf-8") as f:
        colors = json.load(f)
    with open(kitty_file, encoding="utf-8") as f:
        text = f.read()
    bg = colors.get("surface") or colors.get("background") or "#101418"
    primary = colors.get("primary", "#81d5cd")
    dark = luminance(hex_to_rgb(bg)) < 0.2
    new = palette(bg, primary, dark)
    lines = [ln for ln in text.splitlines()
             if not re.match(r"^\s*color\d+\s", ln) and not ln.startswith("# Terminal palette")]
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append("")
    lines.append("# Terminal palette: real hues, made readable on the background (lennox.terminal_colors)")
    for i in range(16):
        lines.append(f"color{i:<3} {new[i]}")
    tmp = kitty_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp, kitty_file)
    return new


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    try:
        rewrite(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    except (OSError, ValueError, KeyError) as e:
        print(f"terminal_colors: {e}", file=sys.stderr)
        sys.exit(1)
