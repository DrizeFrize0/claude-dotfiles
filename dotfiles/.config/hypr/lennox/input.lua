-- -----------------------------------------------------
-- Keyboard, mouse and touchpad
-- -----------------------------------------------------
-- Change these in Lennox Settings > Keyboard & Touchpad.

local i = LENNOX.input
local t = LENNOX.touchpad

hl.config({
    input = {
        kb_layout          = i.kb_layout,
        kb_variant         = i.kb_variant,
        kb_model           = i.kb_model,
        kb_options         = i.kb_options,
        repeat_rate        = i.repeat_rate,
        repeat_delay       = i.repeat_delay,
        numlock_by_default = i.numlock,
        follow_mouse       = i.follow_mouse,
        sensitivity        = i.sensitivity,
        accel_profile      = i.accel_profile,
        natural_scroll     = i.natural_scroll,

        touchpad = {
            natural_scroll          = t.natural_scroll,
            tap_to_click            = t.tap_to_click,
            tap_and_drag            = t.tap_and_drag,
            disable_while_typing    = t.disable_while_typing,
            clickfinger_behavior    = t.clickfinger,
            middle_button_emulation = t.middle_button_emulation,
            scroll_factor           = t.scroll_factor,
        },
    },
})
