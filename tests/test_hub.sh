#!/usr/bin/env bash
# lennox-hub opens the hub page: app window if possible, else the browser. Run: bash tests/test_hub.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D="$SP/../dotfiles/.local"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"; export HOME="$T/h"; unset XDG_CONFIG_HOME
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/lennox" "$HOME/.config/lennox" "$T/bin"
ln -s "$D/share/lennox/python" "$HOME/.local/share/lennox/python"
cp "$D/bin/lennox-hub" "$D/bin/lennox-get" "$HOME/.local/bin/"
printf '#!/bin/sh\necho "$@" >> %s/log\n' "$T" > "$T/bin/notify-send"
printf '#!/bin/sh\necho "browser $@" >> %s/log\n' "$T" > "$HOME/.local/bin/lennox-open"
printf '#!/bin/sh\necho "chromium $@" >> %s/log\n' "$T" > "$T/bin/chromium"
chmod +x "$T/bin/"* "$HOME/.local/bin/"*
export PATH="$T/bin:$PATH"
hub() { : > "$T/log"; bash "$HOME/.local/bin/lennox-hub" "$@"; sleep 0.3; }
hub; check "no address: says so and stops" 'grep -q "Set its address" "$T/log"'
echo '{"hub": {"url": "192.168.1.20:8080"}}' > "$HOME/.config/lennox/settings.json"
hub; check "address without http gets http://, opens as an app" 'grep -q "chromium --app=http://192.168.1.20:8080" "$T/log"'
rm "$T/bin/chromium"
hub; check "no Chromium and no WebKit: falls back to the browser" 'grep -q "browser browser http://192.168.1.20:8080" "$T/log"'
rm -rf "$T"; exit $fail
