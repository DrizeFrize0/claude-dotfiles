-- -----------------------------------------------------
-- Autostart
-- -----------------------------------------------------
-- Everything that runs at login lives in ~/.local/bin/lennox-autostart,
-- which logs to ~/.local/state/lennox/autostart.log.

hl.on("hyprland.start", function()
    -- Let systemd user services (portals, polkit) see the Wayland session
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE")

    -- Password prompts for apps that need admin rights
    hl.exec_cmd("systemctl --user start hyprpolkitagent")

    -- Wallpaper daemon, then the rest of the desktop
    hl.exec_cmd("awww-daemon")
    hl.exec_cmd(HOME .. "/.local/bin/lennox-autostart")
end)
