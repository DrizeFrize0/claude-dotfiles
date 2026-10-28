-- -----------------------------------------------------
-- Misc
-- -----------------------------------------------------

hl.config({
    misc = {
        disable_hyprland_logo      = true,
        disable_splash_rendering   = true,
        force_default_wallpaper    = 0,
        initial_workspace_tracking = 1,
        on_focus_under_fullscreen  = 1,
        allow_session_lock_restore = true,
        focus_on_activate          = true,
        mouse_move_enables_dpms    = true,
        key_press_enables_dpms     = true,
        middle_click_paste         = false,
        vrr                        = 2,
    },

    cursor = {
        hide_on_key_press = true,
        inactive_timeout  = 8,
    },

    ecosystem = {
        no_update_news  = true,
        no_donation_nag = true,
    },
})
