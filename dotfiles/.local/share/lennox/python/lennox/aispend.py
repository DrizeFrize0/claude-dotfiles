"""AI coding spend from CodeBurn, for the bar, with a monthly budget.

    python3 -m lennox.aispend waybar|status|refresh

Reads `codeburn status --format json` (today and this month), at most every
5 minutes because CodeBurn re-reads every log, and warns once a month at
80% and at 100% of the budget in Lennox Settings > Widgets.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import time

from . import settings as S

CACHE = os.path.join(S.CACHE_DIR, "aispend.json")
ALERTS = os.path.join(os.path.expanduser("~/.local/state/lennox"), "aispend-alerts.json")
MAX_AGE = 5 * 60
SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹"}


def money(amount, currency):
    symbol = SYMBOLS.get(currency, "")
    text = f"{amount:,.0f}" if amount >= 100 else f"{amount:,.2f}"
    return f"{symbol}{text}" if symbol else f"{text} {currency}"


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(tmp, path)


def fetch(force=False, now=None):
    """{'currency', 'today', 'month'} (costs), from the cache when it is fresh. None without CodeBurn."""
    now = now or time.time()
    cached = _load_json(CACHE)
    if not force and cached and now - cached.get("time", 0) < MAX_AGE:
        return cached
    if not shutil.which("codeburn"):
        return None
    try:
        out = subprocess.run(["codeburn", "status", "--format", "json"], capture_output=True,
                             text=True, timeout=120)
        raw = json.loads(out.stdout)
        result = {"time": now, "currency": raw.get("currency", "USD"),
                  "today": float(raw["today"]["cost"]), "month": float(raw["month"]["cost"])}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return cached  # keep showing the last good numbers
    _save_json(CACHE, result)
    return result


def check_budget(spend, budget, notify, today=None):
    """Warn once per month at 80% and 100% of the budget. Returns the level sent, if any."""
    if not spend or budget <= 0:
        return None
    month = (today or datetime.date.today()).strftime("%Y-%m")
    state = _load_json(ALERTS) or {}
    if state.get("month") != month:
        state = {"month": month, "sent": []}
    used = spend["month"] / budget * 100
    level = 100 if used >= 100 else 80 if used >= 80 else None
    if level is None or level in state["sent"]:
        return None
    cost, limit = money(spend["month"], spend["currency"]), money(budget, spend["currency"])
    if level == 100:
        notify("AI budget used up", f"{cost} spent on AI coding this month, over your {limit} budget.")
    else:
        notify("AI budget at 80%", f"{cost} of your {limit} monthly AI budget is spent.")
    state["sent"] = sorted(set(state["sent"]) | {80, level})
    _save_json(ALERTS, state)
    return level


def waybar(spend, budget):
    if not spend:
        return {"text": ""}
    cur = spend["currency"]
    tip = [f"AI coding today  {money(spend['today'], cur)}",
           f"This month  {money(spend['month'], cur)}"]
    state = "ok"
    if budget > 0:
        used = spend["month"] / budget * 100
        tip.append(f"Budget  {money(budget, cur)} a month ({used:.0f}% used)")
        state = "over" if used >= 100 else "near" if used >= 80 else "ok"
    tip.append("")
    tip.append("Click: CodeBurn dashboard · Right-click: refresh")
    return {"text": f"󰚩 {money(spend['today'], cur)}", "tooltip": "\n".join(tip), "class": state}


def _notify(title, body):
    subprocess.run(["notify-send", "-a", "Lennox", "-i", "dialog-information", title, body], check=False)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    settings = S.load()
    ai = settings["ai"]
    if mode == "waybar":
        if not ai["spend_widget"]:
            print(json.dumps({"text": ""}))
            return 0
        spend = fetch()
        check_budget(spend, ai["monthly_budget"], _notify)
        print(json.dumps(waybar(spend, ai["monthly_budget"]), ensure_ascii=False))
        return 0
    spend = fetch(force=(mode == "refresh"))
    if spend is None:
        print("CodeBurn's command is not installed (yay -S codeburn)", file=sys.stderr)
        return 1
    print(json.dumps({"currency": spend["currency"], "today": spend["today"], "month": spend["month"],
                      "budget": ai["monthly_budget"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
