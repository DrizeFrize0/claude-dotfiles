-- -----------------------------------------------------
-- Animations
-- -----------------------------------------------------
-- Presets live in lennox/animations/. Pick one in
-- Lennox Settings > Appearance > Animations.

local a = LENNOX.appearance

lennox_preset("animations", a.animations)

if a.animations ~= "off" then
    -- Workspace switch style (Settings > Appearance > Workspace switch)
    local workspace_styles = { slide = true, slidevert = true, fade = true, slidefade = true }
    if workspace_styles[a.workspace_anim] then
        hl.curve("lennox_ws", { type = "bezier", points = { {0.1, 1}, {0, 1} } })
        hl.animation({ leaf = "workspaces", enabled = true, speed = 6, bezier = "lennox_ws", style = a.workspace_anim })
    end

    -- Animated border: the gradient slowly spins around the active window
    if a.border_style == "animated" then
        hl.curve("lennox_linear", { type = "bezier", points = { {0, 0}, {1, 1} } })
        hl.animation({ leaf = "borderangle", enabled = true, speed = 60, bezier = "lennox_linear", style = "loop" })
    end
end
