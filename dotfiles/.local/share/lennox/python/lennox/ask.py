"""Ask Claude from anywhere: a small box, a question, the answer in a small window.

    python3 -m lennox.ask [QUESTION]      opens the window (asks straight away if you give a question)
    python3 -m lennox.ask --print QUESTION  prints the answer (for scripts and tests)

It uses an API key from ANTHROPIC_API_KEY or ~/.config/lennox/anthropic.key
(one line, chmod 600), or else the `claude` command if Claude Code is installed.
The model is in Settings > Extras. The key is only ever sent to Anthropic.
"""

import json
import os
import shutil
import sys
import urllib.error
import urllib.request

from . import settings as S
from . import sh

KEY_FILE = os.path.join(S.CONFIG_DIR, "anthropic.key")
API = os.environ.get("LENNOX_ASK_URL", "https://api.anthropic.com/v1/messages")
SYSTEM = ("You answer quickly for a high school student using Linux. Be short and clear. "
          "Use plain text, no markdown headings.")


def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or sh.read_text(KEY_FILE).strip()


def ask_api(question, model, key, url=None):
    body = json.dumps({"model": model, "max_tokens": 800, "system": SYSTEM,
                       "messages": [{"role": "user", "content": question}]}).encode()
    req = urllib.request.Request(url or API, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:                  # noqa: S310  a fixed https address
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError("The key was refused" if e.code in (401, 403) else f"Anthropic said {e.code}") from e
    except (OSError, ValueError) as e:
        raise RuntimeError("Couldn't reach Anthropic: are you online?") from e
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def ask_cli(question, model):
    code, out, err = sh.run(["claude", "-p", "--model", model, question], 120)
    if code != 0:
        raise RuntimeError(err.strip().splitlines()[-1] if err.strip() else "Claude Code didn't answer")
    return out.strip()


def answer(question, model=None):
    model = model or S.load()["ask"]["model"]
    key = api_key()
    if key:
        return ask_api(question, model, key)
    if shutil.which("claude"):
        return ask_cli(question, model)
    raise RuntimeError(f"No way to ask yet. Put an API key in {KEY_FILE} (one line), or install Claude Code.")


def main(argv):
    args = [a for a in argv[1:] if a != "--print"]
    if "--print" in argv:
        try:
            print(answer(" ".join(args)))
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    from .askwindow import run
    return run(" ".join(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
