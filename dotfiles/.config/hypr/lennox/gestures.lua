-- -----------------------------------------------------
-- Touchpad gestures
-- -----------------------------------------------------
-- 3 fingers left/right   switch workspace
-- 3 fingers up           show the scratchpad
-- 4 fingers pinch out/in fullscreen on/off

if not LENNOX.touchpad.gestures then
    return
end

hl.gesture({
    fingers = 3,
    direction = "horizontal",
    action = "workspace",
})

hl.gesture({
    fingers = 3,
    direction = "up",
    action = "special",
    workspace_name = "scratchpad",
})

hl.gesture({
    fingers = 4,
    direction = "pinchout",
    action = function()
        hl.dispatch(hl.dsp.window.fullscreen({ action = "set" }))
    end,
})

hl.gesture({
    fingers = 4,
    direction = "pinchin",
    action = function()
        hl.dispatch(hl.dsp.window.fullscreen({ action = "unset" }))
    end,
})

hl.config({
    gestures = {
        workspace_swipe_cancel_ratio = 0.3,
        workspace_swipe_create_new = false,
    },
})
