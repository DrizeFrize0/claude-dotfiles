-- -----------------------------------------------------
-- Minimize
-- -----------------------------------------------------
-- Hyprland has no minimize, so minimized windows wait on a hidden
-- workspace (special:minimized). The bar shows how many there are;
-- lennox-minimize brings them back (SUPER + ALT + H).

local HIDDEN = "special:minimized"

-- The minimize button inside apps (and their "restore" requests)
hl.on("window.minimize", function(window, minimize)
    if not window then
        return
    end
    if minimize then
        hl.dispatch(hl.dsp.window.move({ window = window, workspace = HIDDEN, follow = false }))
    else
        local ws = hl.get_active_workspace()
        if ws and ws.id then
            hl.dispatch(hl.dsp.window.move({ window = window, workspace = ws.id, follow = false }))
            hl.dispatch(hl.dsp.focus({ window = window }))
        end
    end
end)
