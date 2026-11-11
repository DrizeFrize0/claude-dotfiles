#!/usr/bin/env bash
# lennox-securedns with sudo, systemctl and getent stubbed. Run: bash tests/test_securedns.sh
R="$(cd "$(dirname "$0")/.." && pwd)"; S="$R/dotfiles/.local/bin/lennox-securedns"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/fs"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
# sudo: log the command; "tee FILE" writes into $T/fs instead of the real /etc
cat > "$T/bin/sudo" <<'X'
#!/usr/bin/env bash
echo "$*" >> "$FAKE/log"
if [ "$1" = tee ]; then mkdir -p "$FAKE/fs$(dirname "$2")"; cat > "$FAKE/fs$2"; fi
exit 0
X
# getent: answers from $FAKE/dns (one "name addr" per line); google turns "bad" once if $FAKE/flaky exists
cat > "$T/bin/getent" <<'X'
#!/usr/bin/env bash
name="$2"
if [ "$name" = www.google.com ] && [ -f "$FAKE/flaky" ]; then rm -f "$FAKE/flaky"; exit 2; fi
grep "^$name " "$FAKE/dns" | while read -r _ a; do echo "$a STREAM $name"; done
X
printf '#!/bin/sh\nexit 0\n' > "$T/bin/sleep"
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" FAKE="$T" LENNOX_SECUREDNS_QUICK=1

printf 'www.netflix.com ::\nwww.google.com 142.250.1.1\nwww.youtube.com 0.0.0.0\n' > "$T/dns"
out="$(bash "$S" test www.netflix.com)"; code=$?
check "a :: answer is reported as blocked" "[ $code -ne 0 ] && grep -q 'BLOCKED  www.netflix.com -> ::' <<<\"\$out\""
out="$(bash "$S" test www.google.com)"
check "a real address is ok" "grep -q 'ok       www.google.com -> 142.250.1.1' <<<\"\$out\""
out="$(bash "$S" test www.youtube.com)"
check "0.0.0.0 is blocked too" "grep -q BLOCKED <<<\"\$out\""

printf 'www.netflix.com 52.1.1.1\nwww.google.com 142.250.1.1\nwww.youtube.com 142.250.2.2\n' > "$T/dns"
out="$(bash "$S" on)"
conf="$T/fs/etc/systemd/resolved.conf.d/lennox-dns.conf"
check "on: strict DNS over TLS to Cloudflare" "grep -q '^DNSOverTLS=yes' $conf && grep -q '1.1.1.1#cloudflare-dns.com' $conf && grep -q '^Domains=~.' $conf"
check "on: NetworkManager stops pushing the network's DNS" "grep -q '^dns=none' $T/fs/etc/NetworkManager/conf.d/lennox-dns.conf"
check "on: resolved enabled and resolv.conf points at it" "grep -q 'systemctl enable --now systemd-resolved' $T/log && grep -q 'ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf' $T/log"
check "on: reports Netflix fixed" "grep -q 'ok       www.netflix.com' <<<\"\$out\" && grep -q '^Done.' <<<\"\$out\""

: > "$T/log"; touch "$T/flaky"
out="$(bash "$S" on)"
check "port 853 blocked: falls back to opportunistic" "grep -q '^DNSOverTLS=opportunistic' $conf && grep -q 'not getting through' <<<\"\$out\""

: > "$T/log"
bash "$S" off >/dev/null
check "off: removes both files and stops resolved" "grep -q 'rm -f /etc/systemd/resolved.conf.d/lennox-dns.conf /etc/NetworkManager/conf.d/lennox-dns.conf' $T/log && grep -q 'disable --now systemd-resolved' $T/log"
out="$(bash "$S" nonsense)"; check "usage on a wrong word" "[ \$? -ne 0 ] || grep -q usage <<<\"\$out\""
# The full check runs lennox.net from the library next to the script (here: the repository)
printf '#!/bin/sh\necho "FULLCHECK $PYTHONPATH $*"\n' > "$T/bin/python3"; chmod +x "$T/bin/python3"
out="$(LENNOX_SECUREDNS_QUICK= bash "$S" test 2>&1)"
check "no SITE: checks every site with lennox.net" "grep -q 'FULLCHECK .*/share/lennox/python -m lennox.net sites' <<<\"\$out\""
out="$(LENNOX_SECUREDNS_QUICK= bash "$S" test www.netflix.com 2>&1)"
check "one SITE: only that one" "! grep -q FULLCHECK <<<\"\$out\""
[ "$fail" = 0 ] && echo "OK securedns" || echo "FAILED securedns"
exit "$fail"
