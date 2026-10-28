-- -----------------------------------------------------
-- Lennox helpers and settings
-- -----------------------------------------------------
-- Loaded first. Defines:
--   HOME     the home directory
--   COLORS   fallback colors (colors.lua replaces them)
--   LENNOX   your settings merged over safe defaults

HOME = os.getenv("HOME")

-- ML4W's default teal scheme, used until the first wallpaper is themed.
COLORS = {
    primary          = "rgba(81d5cdff)",
    on_primary       = "rgba(003734ff)",
    primary_container = "rgba(00504bff)",
    secondary        = "rgba(b0ccc8ff)",
    tertiary         = "rgba(b3c8e8ff)",
    surface          = "rgba(0e1514ff)",
    on_surface       = "rgba(dde4e2ff)",
    outline          = "rgba(899391ff)",
    shadow           = "rgba(000000ff)",
    error            = "rgba(ffb4abff)",
}

-- Every value Lennox reads, with the value used when the setting is
-- missing or has the wrong type. Lennox Settings writes the real values
-- into lennox/settings.lua.
local DEFAULTS = {
    appearance = {
        animations       = "default",
        border_style     = "gradient",
        workspace_anim   = "preset",
        gaps_in          = 8,
        gaps_out         = 14,
        border_size      = 2,
        rounding         = 14,
        active_opacity   = 1.0,
        inactive_opacity = 0.9,
        blur             = true,
        blur_size        = 5,
        blur_passes      = 4,
        shadow           = true,
        dim_inactive     = false,
        layout           = "dwindle",
        cursor_theme     = "Bibata-Modern-Ice",
        cursor_size      = 24,
    },
    display = {
        scale = 1.0,
    },
    input = {
        kb_layout      = "us",
        kb_variant     = "",
        kb_model       = "",
        kb_options     = "grp:alt_shift_toggle",
        repeat_rate    = 35,
        repeat_delay   = 300,
        numlock        = true,
        sensitivity    = 0.0,
        accel_profile  = "",
        natural_scroll = false,
        follow_mouse   = 1,
    },
    touchpad = {
        natural_scroll          = true,
        tap_to_click            = true,
        tap_and_drag            = true,
        disable_while_typing    = true,
        clickfinger             = false,
        middle_button_emulation = false,
        scroll_factor           = 1.0,
        gestures                = true,
    },
    keybinds = {
        main_mod = "SUPER",
    },
}

-- Deep merge `over` into a copy of `base`. Values whose type does not
-- match the default are ignored, so a typo in a settings file can never
-- break Hyprland.
local function merge(base, over)
    local out = {}
    for k, v in pairs(base) do
        out[k] = v
    end
    if type(over) ~= "table" then
        return out
    end
    for k, v in pairs(over) do
        local current = out[k]
        if type(current) == "table" and type(v) == "table" then
            out[k] = merge(current, v)
        elseif current == nil or type(current) == type(v) then
            out[k] = v
        else
            print("[lennox] ignoring setting " .. tostring(k) .. ": expected " .. type(current))
        end
    end
    return out
end

pcall(require, "lennox.settings")
LENNOX = merge(DEFAULTS, LENNOX_SETTINGS)

-- Load a preset file (e.g. lennox/animations/fast.lua), falling back to
-- the default preset if the requested one does not exist.
function lennox_preset(kind, name)
    if type(name) ~= "string" or not name:match("^[%w_]+$") then
        name = "default"
    end
    local ok = pcall(require, "lennox." .. kind .. "." .. name)
    if not ok and name ~= "default" then
        print("[lennox] preset " .. kind .. "/" .. name .. " not found, using default")
        pcall(require, "lennox." .. kind .. ".default")
    end
end
