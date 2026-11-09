"""Static check of the hyprlock styles (no hyprlock here): blocks, keys, variables, sourced files.
Run: python3 tests/test_hyprlock.py"""
import os
import re
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CONF = os.path.join(R, "dotfiles", ".config")
COMMON = {"monitor", "position", "halign", "valign", "zindex", "shadow_passes", "shadow_size", "shadow_color",
          "shadow_boost", "rotate"}
KEYS = {
    "general": {"hide_cursor", "grace", "ignore_empty_input", "immediate_render", "text_trim", "fractional_scaling",
                "screencopy_mode", "fail_timeout", "no_fade_in", "no_fade_out"},
    "animations": {"enabled", "bezier", "animation"},
    "background": COMMON | {"path", "color", "blur_passes", "blur_size", "noise", "contrast", "brightness", "vibrancy",
                            "vibrancy_darkness", "reload_time", "reload_cmd", "crossfade_time"},
    "input-field": COMMON | {"size", "outline_thickness", "dots_size", "dots_spacing", "dots_center", "dots_rounding",
                             "outer_color", "inner_color", "font_color", "font_family", "fade_on_empty", "fade_timeout",
                             "placeholder_text", "hide_input", "rounding", "check_color", "fail_color", "fail_text",
                             "capslock_color", "numlock_color", "bothlock_color", "invert_numlock", "swap_font_color"},
    "label": COMMON | {"text", "text_align", "color", "font_size", "font_family"},
    "image": COMMON | {"path", "size", "rounding", "border_size", "border_color", "reload_time", "reload_cmd"},
    "shape": COMMON | {"size", "color", "rounding", "border_size", "border_color", "xray"},
}
LEAVES = {"global", "fade", "fadeIn", "fadeOut", "inputField", "inputFieldColors", "inputFieldFade",
          "inputFieldWidth", "inputFieldDots"}
RUNTIME = {"TIME", "TIME12", "USER", "ATTEMPTS", "FAIL", "LAYOUT", "DESC", "PROMPT", "HOME", "FPRINTFAIL", "FPRINTPROMPT"}


def colors():
    names = set()
    for line in open(os.path.join(CONF, "hypr", "colors.conf")):
        m = re.match(r"\$(\w+)\s*=", line)
        if m:
            names.add(m.group(1))
    return names


def check(path):
    errors, defined, stack, beziers = [], colors(), [], set()
    for n, raw in enumerate(open(path), 1):
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith(("text", "placeholder_text", "fail_text")) else raw.strip()
        if not line:
            continue
        m = re.match(r"\$(\w+)\s*=", line)
        if m:
            defined.add(m.group(1))
            continue
        if line.endswith("{"):
            block = line[:-1].strip()
            if block not in KEYS:
                errors.append(f"{n}: unknown block {block}")
            stack.append(block)
            continue
        if line == "}":
            if not stack:
                errors.append(f"{n}: stray }}")
            else:
                stack.pop()
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not stack:
            if key == "source":
                target = value.replace("~/.config", CONF)
                if not os.path.exists(target):
                    errors.append(f"{n}: sources a missing file {value}")
            else:
                errors.append(f"{n}: {key} outside a block")
            continue
        if key not in KEYS[stack[-1]]:
            errors.append(f"{n}: {stack[-1]} has no key {key}")
        if key == "bezier":
            beziers.add(value.split(",")[0].strip())
        if key == "animation":
            parts = [p.strip() for p in value.split(",")]
            if parts[0] not in LEAVES:
                errors.append(f"{n}: unknown animation {parts[0]}")
            if len(parts) >= 4 and parts[3] not in beziers | {"default", "linear"}:
                errors.append(f"{n}: curve {parts[3]} is not defined above")
        for var in re.findall(r"\$(\w+)", value):
            if var not in defined and var not in RUNTIME:
                errors.append(f"{n}: ${var} is not defined")
    if stack:
        errors.append("unclosed block " + stack[-1])
    return errors


fail = 0
for name in ("hyprlock.conf", "lock/expressive.conf", "lock/classic.conf"):
    errs = check(os.path.join(CONF, "hypr", name))
    for e in errs:
        print(f"FAIL {name}:{e}")
    fail |= bool(errs)
    if not errs:
        print(f"ok   {name}")
print("OK hyprlock" if not fail else "FAILED hyprlock")
sys.exit(fail)
