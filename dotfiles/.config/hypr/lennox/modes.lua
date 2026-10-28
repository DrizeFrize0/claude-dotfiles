-- -----------------------------------------------------
-- Performance modes
-- -----------------------------------------------------
-- lennox-mode writes the active mode to $XDG_RUNTIME_DIR/lennox/modes
-- and reloads Hyprland, so modes survive config reloads but are reset by
-- a reboot.
--   game    no animations, blur, shadows, gaps or rounding (SUPER + ALT + G)
--   saver   no blur, shadows or transparency (automatic on battery)

local runtime = os.getenv("XDG_RUNTIME_DIR") or "/tmp"

local function mode_active(name)
    local f = io.open(runtime .. "/lennox/modes/" .. name, "r")
    if f then
        f:close()
        return true
    end
    return false
end

if mode_active("saver") then
    hl.config({
        decoration = {
            inactive_opacity = 1.0,
            dim_inactive     = false,
            shadow = { enabled = false },
            blur   = { enabled = false },
        },
    })
end

if mode_active("game") then
    hl.config({
        animations = { enabled = false },
        general = {
            gaps_in     = 0,
            gaps_out    = 0,
            border_size = 1,
        },
        decoration = {
            rounding         = 0,
            active_opacity   = 1.0,
            inactive_opacity = 1.0,
            dim_inactive     = false,
            shadow = { enabled = false },
            blur   = { enabled = false },
        },
    })
end
