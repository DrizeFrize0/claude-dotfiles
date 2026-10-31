"""The settings store used by every page.

Changes are saved to settings.json right away; the matching `lennox-apply`
parts run a moment later, batched, so dragging a slider applies once.
"""

from gi.repository import GLib, GObject

from .. import settings as S
from .util import lennox_bin, run_async


class Store(GObject.Object):
    __gsignals__ = {
        # emitted with the dotted path after a value changed
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # emitted when lennox-apply fails, with the error text
        "apply-failed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    APPLY_DELAY_MS = 450

    def __init__(self):
        super().__init__()
        self.data = S.load()
        self._parts = set()
        self._source = 0

    def reload(self):
        self.data = S.load()

    def get(self, path):
        return S.get(self.data, path)

    def set(self, path, value, apply=True):
        section, _, key = path.partition(".")
        if self.data[section][key] == value:
            return
        self.data[section][key] = value
        self.data = S.save(self.data)
        self.emit("changed", path)
        if apply:
            self._parts.update(S.parts_for(path))
            if self._source:
                GLib.source_remove(self._source)
            self._source = GLib.timeout_add(self.APPLY_DELAY_MS, self._flush)

    def flush_now(self):
        """Apply pending changes immediately (used when the window closes)."""
        if self._source:
            GLib.source_remove(self._source)
            self._flush()

    def _flush(self):
        self._source = 0
        if not self._parts:
            return GLib.SOURCE_REMOVE
        parts = sorted(self._parts)
        self._parts.clear()

        def done(ok, _out, err):
            if not ok:
                self.emit("apply-failed", err.strip() or "lennox-apply failed")

        run_async([lennox_bin("lennox-apply"), *parts], done)
        return GLib.SOURCE_REMOVE
