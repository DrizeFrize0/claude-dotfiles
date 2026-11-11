"""python3 -m lennox.getcli section.key: print one Lennox setting (booleans as true/false)."""

import sys

from . import settings


def main(argv):
    if len(argv) != 2:
        print("usage: lennox-get section.key", file=sys.stderr)
        return 2
    try:
        value = settings.get(settings.load(), argv[1])
    except KeyError:
        print(f"lennox-get: unknown setting {argv[1]}", file=sys.stderr)
        return 1
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
