-- -----------------------------------------------------
-- Environment
-- -----------------------------------------------------
-- The GPU choice (AQ_DRM_DEVICES) is made before Hyprland starts, by
-- /usr/local/bin/lennox-session, so the laptop screen always runs on the
-- Intel GPU and the GTX 1650 can sleep until a game needs it.

local a = LENNOX.appearance

-- Make ~/.local/bin (all lennox-* commands) available to binds and apps
hl.env("PATH", HOME .. "/.local/bin:" .. (os.getenv("PATH") or "/usr/local/bin:/usr/bin"))

-- Cursor
hl.env("XCURSOR_THEME", a.cursor_theme)
hl.env("XCURSOR_SIZE", tostring(a.cursor_size))
hl.env("HYPRCURSOR_SIZE", tostring(a.cursor_size))

-- Toolkits: prefer Wayland, fall back to X11
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
hl.env("CLUTTER_BACKEND", "wayland")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
hl.env("MOZ_ENABLE_WAYLAND", "1")

-- SDL_VIDEODRIVER is deliberately left unset: forcing Wayland breaks
-- some older Steam games, and modern SDL picks Wayland on its own.

hl.config({
    xwayland = {
        force_zero_scaling = true,
    },
})
