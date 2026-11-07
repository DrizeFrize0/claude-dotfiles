"""Clipboard history (cliphist) and pinned snippets, for Lennox Settings > Clipboard."""

import json
import os
import re

from . import settings as S

PINS = os.path.join(S.CONFIG_DIR, "clipboard-pins.json")
MAX_PINS = 30
MAX_PIN_CHARS = 5000
SHOWN = 60
IMAGE = re.compile(r"^\[\[ binary data .*(png|jpe?g|bmp|gif|webp).* \]\]$", re.I)


def parse_list(text):
    """`cliphist list` -> [{'id', 'line', 'text', 'image'}] newest first."""
    items = []
    for line in text.splitlines():
        entry_id, tab, preview = line.partition("\t")
        if not tab or not entry_id.isdigit():
            continue
        items.append({"id": entry_id, "line": line, "text": preview.strip(), "image": bool(IMAGE.match(preview.strip()))})
    return items


def search(items, query, limit=SHOWN):
    words = query.lower().split()
    found = [i for i in items if all(w in i["text"].lower() for w in words)]
    return found[:limit]


def load_pins(path=PINS):
    try:
        with open(path, encoding="utf-8") as f:
            pins = json.load(f)
        return [p for p in pins if isinstance(p, str)][:MAX_PINS] if isinstance(pins, list) else []
    except (OSError, ValueError):
        return []


def save_pins(pins, path=PINS):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(pins[:MAX_PINS], f, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def add_pin(pins, text):
    """Newest pin first; the same text isn't pinned twice; very long text is cut."""
    text = text[:MAX_PIN_CHARS]
    if not text.strip():
        return pins
    return [text] + [p for p in pins if p != text]


def one_line(text, width=90):
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[:width - 1] + "…"
