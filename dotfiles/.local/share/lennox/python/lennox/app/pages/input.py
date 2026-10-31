"""Keyboard, mouse and touchpad."""

import re

from gi.repository import Adw

from .. import rows

SWITCH_KEYS = [
    ("grp:alt_shift_toggle", "Alt + Shift"),
    ("grp:ctrl_shift_toggle", "Ctrl + Shift"),
    ("grp:caps_toggle", "Caps Lock"),
    ("", "No shortcut"),
]


def _layout_ok(text):
    if not re.fullmatch(r"[a-z]{2,3}(,[a-z]{2,3})*", text):
        return "Use layout codes like us, gb, de, fr. Several: us,de"
    return None


def with_layout(layout, variant, code, on):
    """Adds or removes a layout (and its variant slot): ("us", "intl", "ara", True) -> ("us,ara", "intl,")."""
    layouts = [x for x in layout.split(",") if x] or ["us"]
    variants = variant.split(",") if variant else []
    variants += [""] * (len(layouts) - len(variants))
    if on and code not in layouts:
        layouts.append(code)
        variants.append("")
    elif not on and code in layouts and len(layouts) > 1:
        i = layouts.index(code)
        layouts.pop(i)
        variants.pop(i)
    variants = variants[:len(layouts)]
    while variants and not variants[-1]:
        variants.pop()
    return ",".join(layouts), ",".join(variants)


def _variant_ok(text):
    if text and not re.fullmatch(r"[A-Za-z0-9_-]*(,[A-Za-z0-9_-]*)*", text):
        return "Variants look like: intl, nodeadkeys, colemak"
    return None


class Page:
    def __init__(self, ctx):
        store = ctx.store
        page = Adw.PreferencesPage()

        def applied(ok, text):
            ctx.toast(f"Keyboard set to {text}" if ok else text)

        keyboard = Adw.PreferencesGroup(title="Keyboard",
                                        description="With several layouts, switch between them with the shortcut below.")
        arabic = Adw.SwitchRow(title="Arabic keyboard", subtitle="Adds Arabic next to your layout; switch with the "
                                                              "shortcut below. The bar shows which one is on.")
        arabic.set_active("ara" in store.get("input.kb_layout").split(","))

        def toggle_arabic(row, _param):
            layout, variant = with_layout(store.get("input.kb_layout"), store.get("input.kb_variant"), "ara",
                                          row.get_active())
            store.set("input.kb_variant", variant)
            store.set("input.kb_layout", layout)
            ctx.toast(f"Keyboard set to {layout}")

        arabic.connect("notify::active", toggle_arabic)
        store.connect("changed", lambda _s, path: path == "input.kb_layout" and arabic.set_active(
            "ara" in store.get("input.kb_layout").split(",")))
        keyboard.add(arabic)
        keyboard.add(rows.entry_row(store, "input.kb_layout", "Layout (e.g. us, gb, de, fr or us,de)",
                                    _layout_ok, applied))
        keyboard.add(rows.entry_row(store, "input.kb_variant", "Variant (optional, e.g. intl)", _variant_ok, applied))
        keyboard.add(rows.combo_row(store, "input.kb_options", "Switch layouts with", SWITCH_KEYS))
        keyboard.add(rows.spin_row(store, "input.repeat_delay", "Repeat delay", "Milliseconds before a held key repeats",
                                   lower=150, upper=1000, step=25))
        keyboard.add(rows.spin_row(store, "input.repeat_rate", "Repeat speed", "Characters per second",
                                   lower=10, upper=80))
        keyboard.add(rows.switch_row(store, "input.numlock", "Num Lock on at login"))
        page.add(keyboard)

        touchpad = Adw.PreferencesGroup(title="Touchpad")
        touchpad.add(rows.switch_row(store, "touchpad.tap_to_click", "Tap to click",
                                     "1 finger = click, 2 = right click, 3 = middle click"))
        touchpad.add(rows.switch_row(store, "touchpad.natural_scroll", "Natural scrolling",
                                     "Content follows your fingers, like a phone"))
        touchpad.add(rows.switch_row(store, "touchpad.disable_while_typing", "Ignore while typing"))
        touchpad.add(rows.switch_row(store, "touchpad.tap_and_drag", "Tap and drag"))
        touchpad.add(rows.switch_row(store, "touchpad.clickfinger", "Click with fingers",
                                     "Press with 2 fingers to right-click, anywhere on the pad"))
        touchpad.add(rows.spin_row(store, "touchpad.scroll_factor", "Scroll speed", lower=0.1, upper=3.0,
                                   step=0.1, digits=1))
        touchpad.add(rows.switch_row(store, "touchpad.gestures", "Gestures",
                                     "3 fingers sideways: workspaces · 3 up: scratchpad · 4-finger pinch: fullscreen"))
        page.add(touchpad)

        pointer = Adw.PreferencesGroup(title="Pointer speed", description="Applies to the mouse and the touchpad.")
        pointer.add(rows.spin_row(store, "input.sensitivity", "Speed", "-1 slow · 0 default · 1 fast",
                                  lower=-1.0, upper=1.0, step=0.1, digits=1))
        pointer.add(rows.combo_row(store, "input.accel_profile", "Acceleration",
                                   [("", "Default"), ("adaptive", "Adaptive"), ("flat", "Flat (best for games)")]))
        pointer.add(rows.switch_row(store, "input.natural_scroll", "Natural scrolling for the mouse wheel"))
        pointer.add(rows.combo_row(store, "input.follow_mouse", "Focus follows the mouse",
                                   [(1, "Yes (ML4W default)"), (2, "Only on click"), (0, "Never")]))
        page.add(pointer)
        self.widget = page
