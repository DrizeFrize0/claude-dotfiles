-- -----------------------------------------------------
-- Window and layer rules
-- -----------------------------------------------------

-- Small tool windows float in the middle of the screen instead of tiling
local function floating(name, match, w, h, extra)
    local rule = {
        name   = name,
        match  = match,
        float  = true,
        center = true,
        size   = w .. " " .. h,
    }
    for k, v in pairs(extra or {}) do
        rule[k] = v
    end
    hl.window_rule(rule)
end

floating("lennox-settings",  { class = "^(dev\\.lennox\\.Settings)$" },              1080, 720)
floating("pavucontrol",      { class = ".*org\\.pulseaudio\\.pavucontrol.*" },        760, 620)
floating("wiremix",          { class = "^(lennox-wiremix)$" },                       900, 600)
floating("blueman",          { class = "^(\\.?blueman-manager.*)$" },                800, 600)
floating("nm-editor",        { class = "^(nm-connection-editor)$" },                 800, 640)
floating("nwg-look",         { class = "^(nwg-look)$" },                             760, 620)
floating("nwg-displays",     { class = "^(nwg-displays)$" },                         960, 640)
floating("calculator",       { class = "^(org\\.gnome\\.Calculator)$" },             420, 640)
floating("mission-center",   { class = "^(io\\.missioncenter\\.MissionCenter)$" },   1000, 680)
floating("lennox-floating",  { class = "^(lennox-floating)$" },                      1000, 680)
floating("polkit",           { class = "^(hyprpolkitagent|polkit-gnome-authentication-agent-1)$" }, 480, 260, { pin = true })
floating("share-picker",     { class = "^(hyprland-share-picker)$" },                640, 420, { pin = true })
floating("file-picker",      { class = "^(xdg-desktop-portal-gtk)$" },               900, 620)
floating("easyeffects",      { class = "^(com\\.github\\.wwmm\\.easyeffects)$" },    1000, 680)

-- Picture-in-picture videos stay on top and follow you between workspaces
hl.window_rule({
    name  = "picture-in-picture",
    match = { title = "^([Pp]icture[-\\s]?[Ii]n[-\\s]?[Pp]icture)(.*)$" },
    float = true,
    pin   = true,
    no_initial_focus = true,
    keep_aspect_ratio = true,
})

-- Steam's small windows float, the library stays tiled
hl.window_rule({
    name  = "steam-dialogs",
    match = { class = "^(steam)$", title = "^(Friends List|Steam Settings|Steam - News.*|Special Offers)$" },
    float = true,
    center = true,
})

-- Never lock or dim the screen while something is fullscreen (games, videos)
hl.window_rule({
    name  = "idle-inhibit-fullscreen",
    match = { class = ".*" },
    idle_inhibit = "fullscreen",
})

-- Ignore apps that try to maximize themselves
hl.window_rule({
    name  = "suppress-maximize",
    match = { class = ".*" },
    suppress_event = "maximize",
})

-- Fix dragging issues with some XWayland apps
hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})

-- Frosted glass behind the launcher, quick panel, notifications and dock
hl.layer_rule({ name = "blur-rofi",    match = { namespace = "^(rofi)$" },                        blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-swaync",  match = { namespace = "^(swaync-control-center|swaync-notification-window)$" }, blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-waybar",  match = { namespace = "^(waybar)$" },                      blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-dock",    match = { namespace = "^(nwg-dock)$" },                    blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "no-anim-picker", match = { namespace = "^(selection|hyprpicker)$" },       no_anim = true })
