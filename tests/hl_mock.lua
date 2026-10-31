-- Strict mock of Hyprland's Lua API (0.56 docs) to validate the Lennox config.
-- Usage: HOME=... lua5.4 hl_mock.lua CONFIG_DIR
local config_dir = arg[1]
package.path = config_dir .. "/?.lua;" .. package.path

local problems = {}
local function problem(msg)
    problems[#problems + 1] = msg .. "\n" .. debug.traceback("", 3):gsub("\n", "\n    ")
end
local function check(cond, msg) if not cond then problem(msg) end end

local function set(list) local s = {} for _, v in ipairs(list) do s[v] = true end return s end

-- ---------------------------------------------------------------- config options (all verified in the 0.56 wiki)
local OPTIONS = {
    general = { gaps_in = "number|table", gaps_out = "number|table", border_size = "number", resize_on_border = "boolean",
                allow_tearing = "boolean", layout = "string",
                col = { active_border = "string|table", inactive_border = "string|table" } },
    decoration = { rounding = "number", rounding_power = "number", active_opacity = "number", inactive_opacity = "number",
                   fullscreen_opacity = "number", dim_inactive = "boolean", dim_strength = "number",
                   shadow = { enabled = "boolean", range = "number", render_power = "number", color = "string" },
                   blur = { enabled = "boolean", size = "number", passes = "number", new_optimizations = "boolean",
                            ignore_opacity = "boolean", xray = "boolean", vibrancy = "number" } },
    animations = { enabled = "boolean" },
    input = { kb_layout = "string", kb_variant = "string", kb_model = "string", kb_options = "string",
              repeat_rate = "number", repeat_delay = "number", numlock_by_default = "boolean", follow_mouse = "number",
              sensitivity = "number", accel_profile = "string", natural_scroll = "boolean",
              touchpad = { natural_scroll = "boolean", tap_to_click = "boolean", tap_and_drag = "boolean",
                           disable_while_typing = "boolean", clickfinger_behavior = "boolean",
                           middle_button_emulation = "boolean", scroll_factor = "number" } },
    gestures = { workspace_swipe_cancel_ratio = "number", workspace_swipe_create_new = "boolean" },
    dwindle = { preserve_split = "boolean" },
    master = { new_status = "string" },
    binds = { workspace_back_and_forth = "boolean", allow_workspace_cycles = "boolean",
              pass_mouse_when_bound = "boolean", scroll_event_delay = "number" },
    misc = { disable_hyprland_logo = "boolean", disable_splash_rendering = "boolean", force_default_wallpaper = "number",
             initial_workspace_tracking = "number", on_focus_under_fullscreen = "number",
             allow_session_lock_restore = "boolean", focus_on_activate = "boolean", mouse_move_enables_dpms = "boolean",
             key_press_enables_dpms = "boolean", middle_click_paste = "boolean", vrr = "number" },
    cursor = { hide_on_key_press = "boolean", inactive_timeout = "number", no_hardware_cursors = "boolean" },
    ecosystem = { no_update_news = "boolean", no_donation_nag = "boolean" },
    xwayland = { force_zero_scaling = "boolean" },
}
local CONFIG = {}

-- Hyprland 0.57 (what Arch ships now): names and types from its official
-- hl.meta.lua stubs, plus the fixed-word options ("bad value" errors)
dofile((os.getenv("SCHEMA057") or "schema057.lua"))

local function lua_kind(v)
    if type(v) == "number" then
        return (math.type(v) == "integer" or v == math.floor(v)) and "integer" or "number"
    end
    return type(v)
end

local function check_057(tbl, schema, path)
    for k, v in pairs(tbl) do
        local expected = schema and schema[k]
        local where = path .. k
        if expected == nil then
            problem("0.57: unknown config option " .. where)
        elseif type(expected) == "table" then
            if type(v) ~= "table" then problem("0.57: " .. where .. " must be a table") else check_057(v, expected, where .. ".") end
        else
            local kind, ok = lua_kind(v), false
            for t in expected:gmatch("[^|]+") do
                if t == kind or (t == "number" and type(v) == "number") then ok = true end
            end
            check(ok, "0.57: " .. where .. " is " .. kind .. ", expected " .. expected .. " (value " .. tostring(v) .. ")")
            local allowed = ENUM057[where]
            if allowed and type(v) == "string" then
                local good = false
                for _, a in ipairs(allowed) do
                    if v == a or v:sub(1, #a + 1) == a .. " " then good = true end
                end
                check(good, "0.57: bad value \"" .. v .. "\" for " .. where .. ", allowed: " .. table.concat(allowed, ", "))
            end
        end
    end
end

local function check_options(tbl, schema, path)
    for k, v in pairs(tbl) do
        local expected = schema[k]
        local where = path .. k
        if expected == nil then
            problem("unknown config option " .. where)
        elseif type(expected) == "table" then
            if type(v) ~= "table" then problem(where .. " must be a table") else check_options(v, expected, where .. ".") end
        else
            local ok = false
            for t in expected:gmatch("[^|]+") do if type(v) == t then ok = true end end
            check(ok, where .. " has type " .. type(v) .. ", expected " .. expected .. " (value " .. tostring(v) .. ")")
            CONFIG[where] = v
        end
    end
end

-- ---------------------------------------------------------------- dispatchers (0.56 list)
local function D(name, allowed)
    allowed = allowed and set(allowed)
    return function(args, extra)
        if allowed and type(args) == "table" then
            for k in pairs(args) do check(allowed[k], "dispatcher " .. name .. ": unknown arg " .. tostring(k)) end
        end
        return { __dispatcher = name, args = args, extra = extra }
    end
end

local W = { "window" }
local dsp = {
    exec_cmd = function(cmd, rules)
        check(type(cmd) == "string" and #cmd > 0, "exec_cmd needs a command string")
        return { __dispatcher = "exec_cmd", cmd = cmd }
    end,
    exec_raw = D("exec_raw"),
    focus = D("focus", { "direction", "monitor", "workspace", "on_current_monitor", "window", "urgent_or_last", "last" }),
    exit = D("exit"), submap = D("submap"), pass = D("pass", W), send_shortcut = D("send_shortcut"),
    send_key_state = D("send_key_state"), layout = D("layout"), dpms = D("dpms", { "action", "monitor" }),
    event = D("event"), global = D("global"), force_idle = D("force_idle"), no_op = D("no_op"),
    force_renderer_reload = D("force_renderer_reload"), release_input_capture = D("release_input_capture"),
    window = {
        close = D("window.close", W), kill = D("window.kill", W), signal = D("window.signal", { "signal", "window" }),
        float = D("window.float", { "action", "window" }),
        fullscreen = D("window.fullscreen", { "mode", "action", "layout_aware", "window" }),
        fullscreen_state = D("window.fullscreen_state", { "internal", "client", "action", "layout_aware", "window" }),
        pseudo = D("window.pseudo", { "action", "window" }),
        move = D("window.move", { "direction", "group_aware", "workspace", "follow", "monitor", "x", "y", "relative",
                                   "into_group", "into_or_create_group", "out_of_group", "window" }),
        swap = D("window.swap", { "direction", "target", "next", "prev" }),
        center = D("window.center", W), cycle_next = D("window.cycle_next", { "next", "tiled", "floating", "window" }),
        tag = D("window.tag", { "tag", "window" }), clear_tags = D("window.clear_tags", W),
        toggle_swallow = D("window.toggle_swallow"), pin = D("window.pin", { "action", "window" }),
        alter_zorder = D("window.alter_zorder", { "mode", "window" }),
        set_prop = D("window.set_prop", { "prop", "value", "window" }),
        deny_from_group = D("window.deny_from_group", { "action" }), drag = D("window.drag"),
        resize = D("window.resize", { "keep_aspect_ratio", "x", "y", "relative", "window" }),
    },
    workspace = {
        rename = D("workspace.rename", { "workspace", "name" }), move = D("workspace.move", { "workspace", "monitor" }),
        swap_monitors = D("workspace.swap_monitors"),
        toggle_special = function(name)
            check(type(name) == "string" and not name:match("^special:"), "toggle_special takes a bare name")
            return { __dispatcher = "workspace.toggle_special" }
        end,
    },
    group = { toggle = D("group.toggle", W), active = D("group.active"), lock = D("group.lock"),
              move_window = D("group.move_window"), next = D("group.next", W), prev = D("group.prev", W) },
    cursor = { move = D("cursor.move"), move_to_corner = D("cursor.move_to_corner") },
}

local function is_dispatcher(d) return type(d) == "table" and d.__dispatcher ~= nil end

-- ---------------------------------------------------------------- binds
local BIND_FLAGS = set({ "locked", "release", "click", "drag", "long_press", "repeating", "non_consuming",
                         "auto_consuming", "mouse", "transparent", "ignore_mods", "description", "dont_inhibit",
                         "submap_universal", "device", "allow_input_capture" })
local BINDS = {}
local MODS = set({ "SUPER", "CTRL", "ALT", "SHIFT" })

-- ---------------------------------------------------------------- rules
local RULE_MATCH = set({ "class", "content", "focus", "fullscreen", "fullscreen_state_client", "fullscreen_state_internal",
                         "float", "group", "initial_class", "initial_title", "modal", "pin", "tag", "title",
                         "workspace", "xdg_tag", "xwayland" })
local RULE_EFFECTS = set({ "center", "content", "float", "fullscreen", "fullscreen_state", "group", "maximize", "monitor",
                           "move", "no_close_for", "no_initial_focus", "pin", "pseudo", "scrolling_width", "size",
                           "suppress_event", "tile", "workspace", "allows_input", "animation", "border_color",
                           "border_size", "confine_pointer", "dim_around", "decorate", "focus_on_activate",
                           "idle_inhibit", "immediate", "keep_aspect_ratio", "max_size", "min_size",
                           "nearest_neighbor", "no_anim", "no_blur", "no_dim", "no_focus", "no_follow_mouse",
                           "no_max_size", "no_screen_share", "no_shadow", "no_shortcuts_inhibit", "no_vrr",
                           "opacity", "opaque", "force_rgbx", "persistent_size", "render_unfocused", "rounding",
                           "rounding_power", "stay_focused", "sync_fullscreen", "tag", "xray" })
local LAYER_EFFECTS = set({ "above_lock", "animation", "blur", "blur_popups", "dim_around", "ignore_alpha", "no_anim",
                            "no_screen_share", "order", "xray" })
local RULE_NAMES = {}

local function handle()
    return { set_enabled = function() end, is_enabled = function() return true end }
end

-- ---------------------------------------------------------------- animations
local LEAVES = set({ "global", "windows", "windowsIn", "windowsOut", "windowsMove", "layers", "layersIn", "layersOut",
                     "fade", "fadeIn", "fadeOut", "fadeSwitch", "fadeShadow", "fadeDim", "fadeLayers", "fadeLayersIn",
                     "fadeLayersOut", "fadePopups", "fadePopupsIn", "fadePopupsOut", "fadeDpms", "border",
                     "borderangle", "workspaces", "workspacesIn", "workspacesOut", "specialWorkspace",
                     "specialWorkspaceIn", "specialWorkspaceOut", "zoomFactor", "monitorAdded" })
local CURVES = { default = true }

local EVENTS = set({ "config.props_refreshed", "config.reloaded", "config.unload", "hyprland.shutdown", "hyprland.start", "input.keyboard.key", "keybinds.submap", "layer.closed", "layer.opened", "monitor.added", "monitor.focused", "monitor.layout_changed", "monitor.removed", "screenshare.state", "window.active", "window.bell", "window.class", "window.close", "window.destroy", "window.fullscreen", "window.kill", "window.minimize", "window.move_to_workspace", "window.open", "window.open_early", "window.pin", "window.title", "window.update_rules", "window.update_state", "window.urgent", "workspace.active", "workspace.created", "workspace.created_early", "workspace.move_to_monitor", "workspace.removed", "workspace.special_active" })  -- Hyprland 0.57 hl.meta.lua
local START_HANDLERS = {}
local EXECS = {}

-- order-independent key combo ("ALT + SUPER + T" == "SUPER + ALT + T")
function normkeys(keys)
    local parts = {}
    for part in keys:upper():gmatch("[^+]+") do parts[#parts + 1] = (part:gsub("%s", "")) end
    table.sort(parts)
    return table.concat(parts, "+")
end

hl = {
    dsp = dsp,
    config = function(t)
        check(type(t) == "table", "hl.config needs a table")
        for category, values in pairs(t) do
            if OPTIONS[category] == nil then problem("unknown config category " .. category)
            elseif type(values) ~= "table" then problem("config category " .. category .. " must be a table")
            else check_options(values, OPTIONS[category], category .. ".") end
            if type(values) == "table" then check_057(values, SCHEMA057[category], category .. ".") end
        end
    end,
    env = function(k, v)
        check(type(k) == "string" and type(v) == "string", "hl.env(" .. tostring(k) .. ") needs two strings, got " .. type(v))
    end,
    monitor = function(t)
        for k in pairs(t) do check(set({ "output", "mode", "position", "scale" })[k], "hl.monitor: unknown key " .. k) end
        check(type(t.scale) == "number" or type(t.scale) == "string", "monitor scale must be number or string")
    end,
    gesture = function(t)
        check(type(t.fingers) == "number" and t.fingers >= 2 and t.fingers <= 9, "gesture fingers 2-9")
        check(set({ "swipe", "horizontal", "vertical", "left", "right", "up", "down", "pinch", "pinchin", "pinchout" })[t.direction],
              "gesture direction " .. tostring(t.direction))
        local actions = set({ "close", "cursor_zoom", "float", "fullscreen", "move", "resize", "scroll_move", "special", "workspace" })
        check(type(t.action) == "function" or actions[t.action], "gesture action " .. tostring(t.action))
        if t.action == "special" then check(type(t.workspace_name) == "string", "special gesture needs workspace_name") end
        for k in pairs(t) do
            check(set({ "fingers", "direction", "action", "mods", "scale", "disable_inhibit", "workspace_name",
                        "zoom_level", "mode" })[k], "gesture: unknown key " .. k)
        end
    end,
    curve = function(name, t)
        check(t.type == "bezier", "curve " .. name .. ": only bezier is identical in 0.56 and 0.57")
        check(type(t.points) == "table" and #t.points == 2 and #t.points[1] == 2 and #t.points[2] == 2, "curve " .. name .. " needs 2 points")
        CURVES[name] = true
    end,
    animation = function(t)
        check(LEAVES[t.leaf], "unknown animation leaf " .. tostring(t.leaf))
        check(type(t.enabled) == "boolean", "animation enabled must be boolean")
        if t.enabled then
            check(type(t.speed) == "number", "animation " .. tostring(t.leaf) .. " needs speed")
            check(t.bezier ~= nil and CURVES[t.bezier], "animation " .. tostring(t.leaf) .. " uses undefined curve " .. tostring(t.bezier))
            check(t.spring == nil, "spring curves differ between 0.56 and 0.57")
        end
        for k in pairs(t) do check(set({ "leaf", "enabled", "speed", "bezier", "spring", "style" })[k], "animation: unknown key " .. k) end
    end,
    bind = function(keys, action, flags)
        check(type(keys) == "string", "bind keys must be a string")
        for part in keys:gmatch("[^+]+") do
            part = part:gsub("^%s+", ""):gsub("%s+$", "")
            check(#part > 0, "empty key in " .. keys)
        end
        check(type(action) == "function" or is_dispatcher(action), "bind " .. keys .. ": action is not a dispatcher/function")
        for k in pairs(flags or {}) do check(BIND_FLAGS[k], "bind " .. keys .. ": unknown flag " .. k) end
        check(flags and type(flags.description) == "string", "bind " .. keys .. " has no description")
        local norm = normkeys(keys)
        check(not BINDS[norm], "duplicate bind " .. keys)
        do
            local seen = {}
            for part in keys:upper():gmatch("[^+]+") do
                part = part:gsub("%s", "")
                check(not seen[part], "repeated key " .. part .. " in " .. keys)
                seen[part] = true
            end
        end
        BINDS[norm] = (flags or {}).description or true
        return { unbind = function() end, remove = function() end, set_enabled = function() end }
    end,
    unbind = function(keys) BINDS[normkeys(keys)] = nil end,
    window_rule = function(t)
        check(type(t.match) == "table", "window_rule needs match")
        for k in pairs(t.match or {}) do check(RULE_MATCH[k], "window_rule match: unknown prop " .. k) end
        for k, v in pairs(t) do
            if k ~= "name" and k ~= "match" then check(RULE_EFFECTS[k], "window_rule: unknown effect " .. k) end
            if k == "size" or k == "move" then check(type(v) == "string" and v:match("^%S+ %S+$"), "window_rule " .. k .. " should be 'W H'") end
        end
        if t.name then check(not RULE_NAMES[t.name], "duplicate rule name " .. t.name); RULE_NAMES[t.name] = true end
        return handle()
    end,
    layer_rule = function(t)
        for k in pairs(t.match or {}) do check(k == "namespace", "layer_rule match: unknown prop " .. k) end
        for k in pairs(t) do if k ~= "name" and k ~= "match" then check(LAYER_EFFECTS[k], "layer_rule: unknown effect " .. k) end end
        if t.name then check(not RULE_NAMES[t.name], "duplicate rule name " .. t.name); RULE_NAMES[t.name] = true end
        return handle()
    end,
    on = function(event, fn)
        check(EVENTS[event], "unknown event " .. tostring(event))
        check(type(fn) == "function", "hl.on " .. tostring(event) .. " needs a function")
        if event == "hyprland.start" then START_HANDLERS[#START_HANDLERS + 1] = fn end
        if event == "window.minimize" then
            -- Exercise both directions with a fake window, and none
            local win = { address = "0x1", class = "kitty", title = "t" }
            for _, args in ipairs({ { win, true }, { win, false }, { nil, true } }) do
                local ok, err = pcall(fn, args[1], args[2])
                check(ok, "window.minimize handler raised: " .. tostring(err))
            end
        end
    end,
    get_active_workspace = function() return { id = 3, name = "3", active = true } end,
    exec_cmd = function(cmd) check(type(cmd) == "string", "exec_cmd string"); EXECS[#EXECS + 1] = cmd end,
    timer = function(fn, opts)
        check(type(fn) == "function" and type(opts.timeout) == "number" and (opts.type == "oneshot" or opts.type == "repeat"), "timer args")
        return { set_enabled = function() end, is_enabled = function() return true end }
    end,
    dispatch = function(d) check(is_dispatcher(d), "hl.dispatch needs a dispatcher") end,
    device = function(t) check(type(t.name) == "string", "device needs name") end,
}

-- ---------------------------------------------------------------- run
local ok, err = pcall(dofile, config_dir .. "/hyprland.lua")
check(ok, "hyprland.lua raised: " .. tostring(err))
for _, fn in ipairs(START_HANDLERS) do
    local ok2, err2 = pcall(fn)
    check(ok2, "hyprland.start handler raised: " .. tostring(err2))
end
check(LENNOX ~= nil, "LENNOX settings table missing")
check(COLORS ~= nil and COLORS.primary ~= nil, "COLORS missing")

local n = 0
for _ in pairs(BINDS) do n = n + 1 end
print(string.format("binds=%d  options=%d  autostart_cmds=%d  layout=%s  kb=%s  anim=%s",
    n, (function() local c = 0 for _ in pairs(CONFIG) do c = c + 1 end return c end)(), #EXECS,
    tostring(CONFIG["general.layout"]), tostring(CONFIG["input.kb_layout"]), tostring(CONFIG["animations.enabled"])))
if os.getenv("SHOW") then
    for k, v in pairs(CONFIG) do if k:match(os.getenv("SHOW")) then print("  " .. k .. " = " .. tostring(v)) end end
end
if #problems > 0 then
    print("PROBLEMS: " .. #problems)
    for _, p in ipairs(problems) do print("- " .. p) end
    os.exit(1)
end
print("OK")
