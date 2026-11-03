"""Synced lyrics for the island: the line being sung right now.

    python3 -m lennox.lyrics now          the current line of the song playing (for testing)

Lyrics come from lrclib.net (free, no account) the first time a song plays and
are kept in ~/.cache/lennox/lyrics. Arabic lines are shown right to left by the
toolkit on its own.
"""

import bisect
import hashlib
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

from . import settings as S
from . import sh

DIR = os.path.join(S.CACHE_DIR, "lyrics")
URL = os.environ.get("LENNOX_LYRICS_URL", "https://lrclib.net/api/get")
LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)")


def parse_lrc(text):
    """'[01:23.45] hello' lines -> ([seconds], [text]) sorted by time (empty lines kept as '')."""
    rows = []
    for raw in (text or "").splitlines():
        m = LINE.match(raw.strip())
        if m:
            rows.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
    rows.sort(key=lambda r: r[0])
    return [r[0] for r in rows], [r[1] for r in rows]


def line_at(parsed, position):
    """The line sung at `position` seconds ('' before the first line or in a pause)."""
    times, texts = parsed
    i = bisect.bisect_right(times, position) - 1
    return texts[i] if i >= 0 else ""


def _key(artist, title):
    return hashlib.sha1(f"{artist}\0{title}".lower().encode()).hexdigest()[:20]


def _fetch(artist, title, length):
    query = {"artist_name": artist, "track_name": title}
    if length:
        query["duration"] = str(int(length))
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(query), headers={"User-Agent": "Lennox"})
    with urllib.request.urlopen(req, timeout=6) as r:                       # noqa: S310  a fixed https address
        return json.load(r).get("syncedLyrics") or ""


def get(artist, title, length=None, fetch=None, cache_dir=None):
    """Parsed lyrics for a song, from the cache or the network ([] / [] if there are none)."""
    cache_dir = cache_dir or DIR
    path = os.path.join(cache_dir, _key(artist, title) + ".lrc")
    try:
        with open(path, encoding="utf-8") as f:
            return parse_lrc(f.read())
    except OSError:
        pass
    try:
        text = (fetch or _fetch)(artist, title, length)
    except (OSError, ValueError, urllib.error.URLError):
        return [], []                                       # offline: try again next song, nothing cached
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return parse_lrc(text)


class Follower:
    """For the island: asks for a song's lyrics in the background, then answers line(position)."""

    def __init__(self):
        self.key = None
        self.parsed = ([], [])

    def line(self, artist, title, length, position):
        key = (artist, title)
        if key != self.key:
            self.key, self.parsed = key, ([], [])
            if title:
                def work(k=key):
                    result = get(artist, title, length)
                    if self.key == k:
                        self.parsed = result
                threading.Thread(target=work, daemon=True).start()
        return line_at(self.parsed, position)


def main(argv):
    if (argv[1] if len(argv) > 1 else "now") != "now":
        print("usage: lennox-lyrics now", file=sys.stderr)
        return 2
    info = sh.out(["playerctl", "metadata", "--format", "{{artist}}\t{{title}}\t{{mpris:length}}\t{{position}}"], 3).split("\t")
    if len(info) != 4 or not info[1]:
        print("Nothing is playing")
        return 0
    length = int(info[2]) / 1e6 if info[2].isdigit() else None
    pos = int(info[3]) / 1e6 if info[3].isdigit() else 0
    print(line_at(get(info[0], info[1], length), pos) or "(no lyrics)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
