-- -----------------------------------------------------
-- Animations: Expressive (after end-4's illogical-impulse)
-- -----------------------------------------------------
-- Material 3 motion: windows pop in from 60% on the "emphasized decelerate"
-- curve and leave on "accelerate", menus and panels glide in fast and settle
-- softly, workspaces slide. Lively but never slow.

hl.config({ animations = { enabled = true } })

hl.curve("md3_standard", { type = "bezier", points = { {0.2, 0},    {0, 1} } })
hl.curve("md3_decel",    { type = "bezier", points = { {0.05, 0.7}, {0.1, 1} } })
hl.curve("md3_accel",    { type = "bezier", points = { {0.3, 0},    {0.8, 0.15} } })
hl.curve("menu_decel",   { type = "bezier", points = { {0.1, 1},    {0, 1} } })
hl.curve("menu_accel",   { type = "bezier", points = { {0.38, 0.04}, {1, 0.07} } })

hl.animation({ leaf = "global",           enabled = true, speed = 6,   bezier = "md3_standard" })
hl.animation({ leaf = "border",           enabled = true, speed = 6,   bezier = "md3_standard" })
hl.animation({ leaf = "windows",          enabled = true, speed = 3,   bezier = "md3_decel",  style = "popin 60%" })
hl.animation({ leaf = "windowsIn",        enabled = true, speed = 3,   bezier = "md3_decel",  style = "popin 60%" })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 3,   bezier = "md3_accel",  style = "popin 60%" })
hl.animation({ leaf = "fade",             enabled = true, speed = 3,   bezier = "md3_decel" })
hl.animation({ leaf = "layersIn",         enabled = true, speed = 3,   bezier = "menu_decel", style = "slide" })
hl.animation({ leaf = "layersOut",        enabled = true, speed = 1.6, bezier = "menu_accel", style = "fade" })
hl.animation({ leaf = "fadeLayersIn",     enabled = true, speed = 2,   bezier = "menu_decel" })
hl.animation({ leaf = "fadeLayersOut",    enabled = true, speed = 4.5, bezier = "menu_accel" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 7,   bezier = "menu_decel", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3,   bezier = "md3_decel",  style = "slidevert" })
