-- -----------------------------------------------------
-- Look: gaps, borders, rounding, blur, shadows
-- -----------------------------------------------------
-- Values come from Lennox Settings > Appearance. The defaults match the
-- ML4W "Default" decoration and window variations.

local a = LENNOX.appearance
local c = COLORS

local active_border = { colors = { c.primary, c.on_primary }, angle = 90 }
local inactive_border = c.on_primary
local border_size = a.border_size

if a.border_style == "solid" then
    active_border = c.primary
elseif a.border_style == "none" then
    border_size = 0
elseif a.border_style == "animated" then
    -- Spun by lennox/animation.lua
    active_border = { colors = { c.primary, c.tertiary or c.secondary, c.secondary, c.primary }, angle = 45 }
end

hl.config({
    general = {
        gaps_in          = a.gaps_in,
        gaps_out         = a.gaps_out,
        border_size      = border_size,
        resize_on_border = true,
        allow_tearing    = false,
        layout           = a.layout,
        col = {
            active_border   = active_border,
            inactive_border = inactive_border,
        },
    },

    decoration = {
        rounding           = a.rounding,
        rounding_power     = 2,
        active_opacity     = a.active_opacity,
        inactive_opacity   = a.inactive_opacity,
        fullscreen_opacity = 1.0,
        dim_inactive       = a.dim_inactive,
        dim_strength       = 0.15,

        shadow = {
            enabled      = a.shadow,
            range        = 32,
            render_power = 2,
            color        = "rgba(00000050)",
        },

        blur = {
            enabled           = a.blur,
            size              = a.blur_size,
            passes            = a.blur_passes,
            new_optimizations = true,
            ignore_opacity    = true,
            xray              = true,
            vibrancy          = 0.1696,
        },
    },
})
