-- -----------------------------------------------------
-- Keybindings
-- -----------------------------------------------------
-- Press SUPER + CTRL + K at any time to search all of these.
-- To change one, unbind it in ~/.config/hypr/custom.lua and bind again:
--   hl.unbind("SUPER + B")
--   hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"))

local mod = LENNOX.keybinds.main_mod
local bin = HOME .. "/.local/bin/"

local function run(cmd)
    return hl.dsp.exec_cmd(bin .. cmd)
end

-- The second modifier in a combo is ALT. If ALT is the main key, the two
-- swap (ALT + G becomes ALT + SUPER + G) so no shortcut is bound twice.
local alt = mod == "ALT" and "SUPER" or "ALT"

local function key(combo)
    return mod .. " + " .. (combo:gsub("ALT", alt))
end

-- Applications ----------------------------------------
hl.bind(key("RETURN"),         run("lennox-open terminal"),    { description = "Open the terminal" })
hl.bind(key("B"),              run("lennox-open browser"),     { description = "Open the browser" })
hl.bind(key("E"),              run("lennox-open filemanager"), { description = "Open the file manager" })
hl.bind(key("C"),              run("lennox-open calculator"),  { description = "Open the calculator" })
hl.bind(key("CTRL + E"),       run("lennox-menu emoji"),       { description = "Emoji picker" })
hl.bind(key("SPACE"),          run("lennox-menu apps"),        { description = "Open the app launcher" })
hl.bind(key("CTRL + RETURN"),  run("lennox-menu apps"),        { description = "Open the app launcher" })
hl.bind(key("TAB"),            run("lennox-menu windows"),     { description = "Switch to an open window" })
hl.bind(key("V"),              run("lennox-menu clipboard"),   { description = "Clipboard history" })
hl.bind(key("CTRL + K"),       run("lennox-menu keybinds"),    { description = "Show all keybindings" })

-- Lennox ----------------------------------------------
hl.bind(key("I"),              run("lennox-settings"),          { description = "Open Lennox Settings" })
hl.bind(key("N"),              run("lennox-panel toggle"),      { description = "Open the quick panel" })
hl.bind(key("D"),              run("lennox-widgets dashboard"), { description = "Open the dashboard" })
hl.bind(key("CTRL + W"),       run("lennox-widgets desktop"),   { description = "Show / hide the desktop widgets" })
hl.bind(key("SHIFT + C"),      run("lennox-colorpicker"),       { description = "Pick a color on screen (copied)" })
hl.bind(key("CTRL + S"),       run("lennox-panel toggle"),      { description = "Open the quick panel" })
hl.bind(key("W"),              run("lennox-menu wallpaper"),    { description = "Pick a wallpaper" })
hl.bind(key("SHIFT + W"),      run("lennox-wallpaper --random"), { description = "Random wallpaper" })
hl.bind(key("CTRL + T"),       run("lennox-menu bar-style"),    { description = "Change the bar style" })
hl.bind(key("SHIFT + M"),      run("lennox-theme toggle"),      { description = "Switch dark / light mode" })
hl.bind(key("SHIFT + H"),      run("lennox-nightlight toggle"), { description = "Night light on / off" })
hl.bind(key("ALT + G"),        run("lennox-mode game toggle"),  { description = "Game mode on / off" })
hl.bind(key("SHIFT + B"),      run("lennox-bar reload"),        { description = "Reload the bar" })
hl.bind(key("CTRL + B"),       run("lennox-bar toggle"),        { description = "Show / hide the bar" })
hl.bind(key("CTRL + D"),       run("lennox-dock toggle"),       { description = "Show / hide the dock" })
hl.bind(key("SHIFT + R"),      hl.dsp.exec_cmd("hyprctl reload"), { description = "Reload Hyprland" })

-- Session ---------------------------------------------
hl.bind(key("L"),              run("lennox-power lock"),        { description = "Lock the screen" })
hl.bind(key("CTRL + L"),       run("lennox-power lock"),        { description = "Lock the screen" })
hl.bind(key("ESCAPE"),         run("lennox-menu power"),        { description = "Power menu" })
hl.bind(key("ALT + R"),        run("lennox-clips save"),        { description = "Save the last 2 minutes of gameplay (clip)" })
hl.bind(key("ALT + P"),        run("lennox-perf cycle"),        { description = "Performance: Quiet / Balanced / Max" })
hl.bind(key("ALT + C"),        run("lennox-clock"),             { description = "Clock: timers, alarms, reminders" })
hl.bind(key("CTRL + ESCAPE"),  run("lennox-open system_monitor"), { description = "System monitor (like Task Manager)" })
hl.bind(key("CTRL + P"),       run("lennox-menu power"),        { description = "Power menu" })

-- Screenshots -----------------------------------------
hl.bind("PRINT",               run("lennox-screenshot area"),   { description = "Screenshot an area (copied and saved)" })
hl.bind(key("PRINT"),          run("lennox-screenshot menu"),   { description = "Screenshot menu" })
hl.bind(key("ALT + F"),        run("lennox-screenshot screen"), { description = "Screenshot the whole screen" })
hl.bind(key("ALT + S"),        run("lennox-screenshot area"),   { description = "Screenshot an area" })
hl.bind(key("ALT + W"),        run("lennox-screenshot window"), { description = "Screenshot the active window" })

-- Windows ---------------------------------------------
hl.bind(key("Q"),              hl.dsp.window.close(),                                         { description = "Close the window" })
hl.bind(key("SHIFT + Q"),      hl.dsp.window.kill(),                                          { description = "Force quit the window" })
hl.bind(key("F"),              hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }), { description = "Fullscreen" })
hl.bind(key("M"),              hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }),  { description = "Maximize" })
hl.bind(key("T"),              hl.dsp.window.float({ action = "toggle" }),                    { description = "Float / tile the window" })
hl.bind(key("SHIFT + T"),      run("lennox-windows toggle"),                                  { description = "Tiling / stacking windows (overlap like Windows)" })
hl.bind(key("ALT + T"), function()
    hl.dispatch(hl.dsp.window.float({ action = "toggle" }))
    hl.dispatch(hl.dsp.window.pin({ action = "toggle" }))
end, { description = "Float and pin the window on all workspaces" })
hl.bind(key("SHIFT + P"),      hl.dsp.window.pseudo({ action = "toggle" }),                   { description = "Pseudo-tile the window" })
hl.bind(key("P"),              run("lennox-passwords fill"),                                  { description = "Fill a password (Bitwarden)" })
hl.bind(key("J"),              hl.dsp.layout("togglesplit"),                                  { description = "Flip the split direction" })
hl.bind(key("K"),              hl.dsp.layout("swapsplit"),                                    { description = "Swap the two halves" })
hl.bind(key("G"),              hl.dsp.group.toggle(),                                         { description = "Group windows into tabs" })

for _, dir in ipairs({ "left", "right", "up", "down" }) do
    hl.bind(key(dir),          hl.dsp.focus({ direction = dir }),       { description = "Focus the window " .. dir })
    hl.bind(key("ALT + " .. dir), hl.dsp.window.swap({ direction = dir:sub(1, 1) }), { description = "Swap with the window " .. dir })
    hl.bind(key("CTRL + " .. dir), hl.dsp.window.move({ direction = dir }), { description = "Move the window " .. dir })
end

local resize_step = {
    left  = { x = -60, y = 0 },
    right = { x = 60,  y = 0 },
    up    = { x = 0,   y = -60 },
    down  = { x = 0,   y = 60 },
}
for dir, delta in pairs(resize_step) do
    hl.bind(key("SHIFT + " .. dir), hl.dsp.window.resize({ x = delta.x, y = delta.y, relative = true }),
        { repeating = true, description = "Resize the window (" .. dir .. ")" })
end

hl.bind(key("mouse:272"), hl.dsp.window.drag(),   { mouse = true, description = "Move a window with the mouse" })
hl.bind(key("mouse:273"), hl.dsp.window.resize(), { mouse = true, description = "Resize a window with the mouse" })

hl.bind(alt .. " + TAB", function()
    hl.dispatch(hl.dsp.window.cycle_next())
    hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top" }))
end, { description = "Cycle windows on this workspace" })

-- Workspaces ------------------------------------------
-- AZERTY keyboards need Shift for digits, so bind the unshifted keys.
local azerty = {
    fr = { "ampersand", "eacute", "quotedbl", "apostrophe", "parenleft",
           "minus", "egrave", "underscore", "ccedilla", "agrave" },
    be = { "ampersand", "eacute", "quotedbl", "apostrophe", "parenleft",
           "section", "egrave", "exclam", "ccedilla", "agrave" },
}
local layout = (LENNOX.input.kb_layout:match("^([^,]+)") or "us"):lower()
local ws_keys = azerty[layout]
if ws_keys and LENNOX.input.kb_variant ~= "" and not LENNOX.input.kb_variant:match("^,") then
    -- Variants such as fr(bepo) or fr(us) are not AZERTY
    local variant = LENNOX.input.kb_variant:match("^([^,]+)")
    if variant ~= "azerty" and variant ~= "oss" and variant ~= "latin9" then
        ws_keys = nil
    end
end

for i = 1, 10 do
    local k = ws_keys and ws_keys[i] or tostring(i % 10)
    hl.bind(key(k),              hl.dsp.focus({ workspace = i }),                      { description = "Go to workspace " .. i })
    hl.bind(key("SHIFT + " .. k), hl.dsp.window.move({ workspace = i }),               { description = "Move the window to workspace " .. i })
    hl.bind(key("CTRL + SHIFT + " .. k), hl.dsp.window.move({ workspace = i, follow = false }), { description = "Send the window to workspace " .. i .. " quietly" })
end

hl.bind(key("H"),         hl.dsp.window.move({ workspace = "special:minimized", follow = false }), { description = "Minimize the window" })
hl.bind(key("ALT + H"),   run("lennox-minimize menu"),                          { description = "Bring back a minimized window" })
hl.bind(key("S"),         hl.dsp.workspace.toggle_special("scratchpad"),       { description = "Show / hide the scratchpad" })
hl.bind(key("SHIFT + S"), hl.dsp.window.move({ workspace = "special:scratchpad" }), { description = "Move the window to the scratchpad" })

-- SUPER + mouse wheel flips through workspaces (one step per notch)
local scroll_locked = false
local function throttled(dispatcher)
    return function()
        if scroll_locked then
            return
        end
        scroll_locked = true
        hl.dispatch(dispatcher)
        hl.timer(function()
            scroll_locked = false
        end, { timeout = 200, type = "oneshot" })
    end
end
hl.bind(key("mouse_down"), throttled(hl.dsp.focus({ workspace = "e+1" })), { description = "Next workspace" })
hl.bind(key("mouse_up"),   throttled(hl.dsp.focus({ workspace = "e-1" })), { description = "Previous workspace" })

-- Laptop keys -----------------------------------------
hl.bind("XF86AudioRaiseVolume",  run("lennox-osd volume up"),      { locked = true, repeating = true, description = "Volume up" })
hl.bind("XF86AudioLowerVolume",  run("lennox-osd volume down"),    { locked = true, repeating = true, description = "Volume down" })
hl.bind("XF86AudioMute",         run("lennox-osd volume mute"),    { locked = true, description = "Mute" })
hl.bind("XF86AudioMicMute",      run("lennox-osd mic mute"),       { locked = true, description = "Mute the microphone" })
hl.bind("XF86MonBrightnessUp",   run("lennox-osd brightness up"),  { locked = true, repeating = true, description = "Brightness up" })
hl.bind("XF86MonBrightnessDown", run("lennox-osd brightness down"), { locked = true, repeating = true, description = "Brightness down" })
hl.bind("XF86KbdBrightnessUp",   run("lennox-osd keyboard up"),    { locked = true, repeating = true, description = "Keyboard light up" })
hl.bind("XF86KbdBrightnessDown", run("lennox-osd keyboard down"),  { locked = true, repeating = true, description = "Keyboard light down" })
hl.bind("XF86TouchpadToggle",    run("lennox-touchpad toggle"),    { locked = true, description = "Touchpad on / off" })
hl.bind("XF86Calculator",        run("lennox-open calculator"),    { description = "Open the calculator" })

hl.bind("XF86AudioPlay",  hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play / pause" })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play / pause" })
hl.bind("XF86AudioNext",  hl.dsp.exec_cmd("playerctl next"),       { locked = true, description = "Next track" })
hl.bind("XF86AudioPrev",  hl.dsp.exec_cmd("playerctl previous"),   { locked = true, description = "Previous track" })
