import os
"""Tiny stand-in for matugen's template engine, used to (1) validate the
Lennox templates and (2) render the first-boot default color files from
ML4W's default palette. Supports exactly the syntax Lennox templates use."""
import json, re, sys, os

ML4W = os.environ.get("SP", os.path.dirname(os.path.abspath(__file__))) + "/ref/ml4w/dotfiles/.config/ml4w/colors/colors.json"
colors = json.load(open(ML4W))
base16 = {  # neutral dark base16 used only for first-boot defaults
 "base00":"#161d1c","base01":"#1f2726","base02":"#2b3332","base03":"#5d6a68","base04":"#8a9896","base05":"#dde4e2","base06":"#e8eeec","base07":"#f4f8f7",
 "base08":"#e57e7e","base09":"#e6a56f","base0a":"#e3cf7c","base0b":"#8fd18f","base0c":"#81d5cd","base0d":"#86b7e8","base0e":"#c69ae6","base0f":"#c48f6e"}

def hex2rgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))
def fmt(h, field):
    if field=="hex": return h.lower()
    if field=="hex_stripped": return h.lstrip('#').lower()
    if field=="rgba": r,g,b=hex2rgb(h); return f"rgba({r}, {g}, {b}, 1)"
    raise KeyError(field)

def resolve(expr, scope):
    expr=expr.strip()
    filt=None
    if '|' in expr:
        expr, filt = [x.strip() for x in expr.split('|',1)]
    parts=expr.split('.')
    if parts[0]=="colors":
        name, variant, field = parts[1], parts[2], parts[3]
        assert variant in ("default","dark","light"), expr
        val = fmt(colors[name], field)
    elif parts[0]=="base16":
        name, variant, field = parts[1], parts[2], parts[3]
        val = fmt(base16[name], field)
    elif parts[0]=="name" and len(parts)==1:
        val = scope["name"]
    elif parts[0]=="value":
        variant, field = parts[1], parts[2]
        val = fmt(scope["value"], field)
    else:
        raise KeyError(f"unknown expression {expr!r}")
    if filt:
        m=re.fullmatch(r'set_alpha:\s*([0-9.]+)', filt)
        assert m, f"unknown filter {filt}"
        assert val.startswith("rgba("), "set_alpha needs rgba"
        val = re.sub(r', [0-9.]+\)$', f", {m.group(1)})", val)
    return val

def render(text):
    def loop(m):
        body=m.group(1)
        out=[]
        for name, value in colors.items():
            out.append(re.sub(r'\{\{(.*?)\}\}', lambda e: resolve(e.group(1), {"name":name,"value":value}), body))
        return "".join(out)
    text = re.sub(r'<\* for name, value in colors \*>(.*?)<\* endfor \*>', loop, text, flags=re.S)
    assert '<*' not in text, "unhandled block"
    return re.sub(r'\{\{(.*?)\}\}', lambda e: resolve(e.group(1), {}), text)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    out = render(open(src).read())
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w").write(out)
