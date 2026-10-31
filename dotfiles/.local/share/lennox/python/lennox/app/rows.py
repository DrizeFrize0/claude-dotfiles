"""Preference rows that read and write a setting in the store."""

from gi.repository import Adw, Gtk


def _subtitle(row, subtitle):
    if subtitle:
        row.set_subtitle(subtitle)


def _follow(store, path, update):
    """Keep a row in sync when the setting changes elsewhere (e.g. a preset).
    Store.set ignores unchanged values, so this cannot loop."""
    store.connect("changed", lambda _s, changed: changed == path and update(store.get(path)))


def switch_row(store, path, title, subtitle=None):
    row = Adw.SwitchRow(title=title)
    _subtitle(row, subtitle)
    row.set_active(bool(store.get(path)))
    row.connect("notify::active", lambda r, _p: store.set(path, r.get_active()))
    _follow(store, path, lambda v: row.set_active(bool(v)))
    return row


def spin_row(store, path, title, subtitle=None, lower=0, upper=100, step=1, digits=0):
    adjustment = Gtk.Adjustment(lower=lower, upper=upper, step_increment=step, page_increment=step * 5)
    row = Adw.SpinRow(title=title, adjustment=adjustment, digits=digits, numeric=True)
    _subtitle(row, subtitle)
    row.set_value(store.get(path))

    def changed(r, _p):
        value = r.get_value()
        store.set(path, round(value, digits) if digits else int(round(value)))

    row.connect("notify::value", changed)
    _follow(store, path, row.set_value)
    return row


def combo_row(store, path, title, choices, subtitle=None, on_change=None):
    """choices: list of (value, label)."""
    row = Adw.ComboRow(title=title)
    _subtitle(row, subtitle)
    row.set_model(Gtk.StringList.new([label for _, label in choices]))
    values = [value for value, _ in choices]
    current = store.get(path)
    if current in values:
        row.set_selected(values.index(current))

    def changed(r, _p):
        index = r.get_selected()
        if 0 <= index < len(values):
            store.set(path, values[index])
            if on_change:
                on_change(values[index])

    row.connect("notify::selected", changed)
    _follow(store, path, lambda v: v in values and row.set_selected(values.index(v)))
    return row


def entry_row(store, path, title, validate=None, on_applied=None):
    """Text setting with an apply (✓) button. validate(text) -> error text or None."""
    row = Adw.EntryRow(title=title, show_apply_button=True)
    row.set_text(str(store.get(path)))

    def applied(r):
        text = r.get_text().strip()
        error = validate(text) if validate else None
        if error:
            r.add_css_class("error")
            r.set_tooltip_text(error)
            if on_applied:
                on_applied(False, error)
            return
        r.remove_css_class("error")
        r.set_tooltip_text(None)
        store.set(path, text)
        if on_applied:
            on_applied(True, text)

    row.connect("apply", applied)
    _follow(store, path, lambda v: row.set_text(str(v)))
    return row


def time_choices():
    """Every quarter hour of the day, for time pickers (smart bedtime moves in 15 minutes)."""
    return [(f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d}") for h in range(24) for m in (0, 15, 30, 45)]


def time_row(store, path, title, subtitle=None):
    choices = time_choices()
    current = store.get(path)
    if current not in [value for value, _ in choices]:
        choices.append((current, current))
        choices.sort()
    return combo_row(store, path, title, choices, subtitle)


def button_row(title, subtitle, button_label, callback, icon=None, suggested=False):
    row = Adw.ActionRow(title=title)
    _subtitle(row, subtitle)
    button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
    if suggested:
        button.add_css_class("suggested-action")
    button.connect("clicked", lambda _b: callback())
    row.add_suffix(button)
    if icon:
        row.add_prefix(Gtk.Image.new_from_icon_name(icon))
    return row


def link_row(title, subtitle, callback, icon=None):
    """A row that opens something when clicked (with an arrow)."""
    row = Adw.ActionRow(title=title, activatable=True)
    _subtitle(row, subtitle)
    if icon:
        row.add_prefix(Gtk.Image.new_from_icon_name(icon))
    row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
    row.connect("activated", lambda _r: callback())
    return row


def info_row(title, value=""):
    # Titles can hold device names (e.g. "HDA Intel & ..."): plain text, not markup
    row = Adw.ActionRow(title=title, use_markup=False)
    label = Gtk.Label(label=value, xalign=1, wrap=True, selectable=True)
    label.add_css_class("dim-label")
    row.add_suffix(label)
    row.value_label = label
    return row


def scale_row(title, subtitle, lower, upper, value, on_change, step=1):
    """A row with a slider (volume, brightness). on_change(value) is debounced by the caller."""
    row = Adw.ActionRow(title=title)
    _subtitle(row, subtitle)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lower, upper, step)
    scale.set_hexpand(True)
    scale.set_size_request(220, -1)
    scale.set_draw_value(True)
    scale.set_value_pos(Gtk.PositionType.RIGHT)
    scale.set_digits(0)
    scale.set_value(value)
    scale.connect("value-changed", lambda s: on_change(s.get_value()))
    row.add_suffix(scale)
    row.scale = scale
    return row
