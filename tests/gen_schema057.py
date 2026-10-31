"""Build a Lua schema of Hyprland's config options from the official hl.meta.lua stubs."""
import re, sys
meta = open(sys.argv[1]).read()
classes = {}
for m in re.finditer(r"---@class (HL\.ConfigOpt[\w.]*)\n((?:---@field .*\n)*)", meta):
    fields = {}
    for f in re.finditer(r"---@field (\w+)\? (.+)", m.group(2)):
        fields[f.group(1)] = f.group(2).strip()
    classes[m.group(1)] = fields

def lua_type(t):
    if t.startswith("HL.ConfigOpt"):
        return None  # nested class
    out = set()
    for part in t.split("|"):
        part = part.strip()
        if part in ("integer",): out.add("integer")
        elif part == "number": out.add("number")
        elif part == "boolean": out.add("boolean")
        elif part == "string": out.add("string")
        elif part == "HL.CssGap": out |= {"integer", "table"}
        elif part == "HL.Gradient": out |= {"string", "table"}
        elif part == "HL.Vec2Like": out |= {"table", "string", "number"}
        else: raise SystemExit("unknown type " + part)
    return "|".join(sorted(out))

def emit(cls, indent):
    lines = []
    for name, t in classes[cls].items():
        if t.startswith("HL.ConfigOpt"):
            lines.append(f'{indent}["{name}"] = {{')
            lines += emit(t, indent + "    ")
            lines.append(f"{indent}}},")
        else:
            lines.append(f'{indent}["{name}"] = "{lua_type(t)}",')
    return lines

print("-- Generated from Hyprland 0.57.0 hl.meta.lua by gen_schema057.py")
print("SCHEMA057 = {")
print("\n".join(emit("HL.ConfigOpt", "    ")))
print("}")
# String options that only accept fixed words (from the 0.57 option descriptions)
print('''ENUM057 = {
    ["general.layout"] = { "dwindle", "master", "scrolling", "monocle" },
    ["input.accel_profile"] = { "adaptive", "flat", "custom" },
    ["input.scroll_method"] = { "2fg", "edge", "on_button_down", "no_scroll" },
    ["input.touchpad.tap_button_map"] = { "lrm", "lmr" },
    ["master.new_status"] = { "master", "slave", "inherit" },
}''')
