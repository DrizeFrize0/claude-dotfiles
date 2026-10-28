-- -----------------------------------------------------
-- Animations: Bouncy
-- -----------------------------------------------------
-- Playful overshoot on windows and workspaces.

hl.config({ animations = { enabled = true } })

hl.curve("overshot",  { type = "bezier", points = { {0.05, 0.9}, {0.1, 1.1} } })
hl.curve("md3_decel", { type = "bezier", points = { {0.05, 0.7}, {0.1, 1} } })
hl.curve("md3_accel", { type = "bezier", points = { {0.3, 0}, {0.8, 0.15} } })

hl.animation({ leaf = "windows",          enabled = true, speed = 4,   bezier = "overshot",  style = "popin 50%" })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 3,   bezier = "md3_accel", style = "popin 60%" })
hl.animation({ leaf = "border",           enabled = true, speed = 10,  bezier = "default" })
hl.animation({ leaf = "fade",             enabled = true, speed = 3,   bezier = "md3_decel" })
hl.animation({ leaf = "layers",           enabled = true, speed = 3,   bezier = "overshot",  style = "slide" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 5,   bezier = "overshot",  style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 4,   bezier = "overshot",  style = "slidevert" })
