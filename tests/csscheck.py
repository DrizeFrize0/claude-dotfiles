import sys, gi
ver = sys.argv[1]
gi.require_version("Gtk", ver)
from gi.repository import Gtk
bad = 0
for path in sys.argv[2:]:
    errors = []
    p = Gtk.CssProvider()
    p.connect("parsing-error", lambda _p, section, err: errors.append(
        f"{section.get_file().get_path() if section.get_file() else '?'}:{section.get_start_location().lines + 1 if ver == '4.0' else section.get_start_line() + 1}: {err.message}"))
    try:
        p.load_from_path(path)
    except Exception as e:
        errors.append(str(e))
    status = "OK " if not errors else "ERR"
    print(f"{status} GTK{ver[0]} {path.split('/.config/')[-1]}")
    for e in errors:
        print("     ", e)
    bad += bool(errors)
sys.exit(1 if bad else 0)
