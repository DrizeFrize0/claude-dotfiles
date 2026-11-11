-- -----------------------------------------------------
-- Monitor fallback
-- -----------------------------------------------------
-- Any screen gets its best resolution and refresh rate. To arrange
-- several screens, open Lennox Settings > Display > "Arrange displays"
-- (nwg-displays). It writes ~/.config/hypr/monitors.lua, which loads
-- after this file and takes priority.

hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = LENNOX.display.scale,
})
