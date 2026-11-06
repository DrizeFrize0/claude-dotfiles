-- -----------------------------------------------------
-- Animations: Subtle
-- -----------------------------------------------------
-- Short, soft motion that never gets in the way: windows ease in, fades
-- are quick, workspaces cross-fade. Light on the GPU.

hl.config({ animations = { enabled = true } })

hl.curve("lennox_out",  { type = "bezier", points = { {0.22, 1}, {0.36, 1} } })
hl.curve("lennox_soft", { type = "bezier", points = { {0.4, 0}, {0.2, 1} } })

hl.animation({ leaf = "global",           enabled = true, speed = 4,   bezier = "lennox_out" })
hl.animation({ leaf = "border",           enabled = true, speed = 4,   bezier = "lennox_out" })
hl.animation({ leaf = "windows",          enabled = true, speed = 3.2, bezier = "lennox_out" })
hl.animation({ leaf = "windowsIn",        enabled = true, speed = 3.2, bezier = "lennox_out", style = "popin 94%" })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 2.4, bezier = "lennox_soft", style = "popin 94%" })
hl.animation({ leaf = "fade",             enabled = true, speed = 2.4, bezier = "lennox_soft" })
hl.animation({ leaf = "layers",           enabled = true, speed = 3,   bezier = "lennox_out" })
hl.animation({ leaf = "layersIn",         enabled = true, speed = 3,   bezier = "lennox_out", style = "fade" })
hl.animation({ leaf = "layersOut",        enabled = true, speed = 2.2, bezier = "lennox_soft", style = "fade" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 3,   bezier = "lennox_out", style = "fade" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3,   bezier = "lennox_out", style = "slidevert" })
