#!/usr/bin/env bash
R="${R:-$(cd "$SP/.." && pwd)}"
SP="${SP:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
# Functional test of lennox-passwords with fake rbw/rofi-rbw
S=$SP; P=$S/pw
LP=$R/dotfiles/.local/bin/lennox-passwords
export PWTEST=$P HOME=$P/home PATH="$P/bin:$PATH"
fails=0
ok() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }
reset() { rm -rf $P/state $P/home/Downloads; mkdir -p $P/state $P/home/Downloads; }

reset
ok "status before setup" '[[ $($LP status) == "{\"installed\":true,\"email\":\"\",\"region\":\"us\",\"unlocked\":false}" ]]'
$LP fill; ok "fill unconfigured opens settings" 'grep -q "lennox-settings --page passwords" $P/state/log && ! grep -q "^rofi-rbw" $P/state/log'
ok "setup rejects bad email" '! $LP setup notanemail 2>/dev/null'
$LP setup me@example.com eu
ok "setup email" '[[ $(jq -r .email $P/state/config.json) == me@example.com ]]'
ok "setup eu base_url" '[[ $(jq -r .base_url $P/state/config.json) == https://api.bitwarden.eu ]]'
ok "setup lock_timeout" '[[ $(jq -r .lock_timeout $P/state/config.json) == 900 ]]'
ok "setup pinentry" '[[ $(jq -r .pinentry $P/state/config.json) == pinentry-gnome3 ]]'
ok "setup opened kitty" 'grep -q "^kitty --class lennox-floating --title Connect Bitwarden bash -c" $P/state/log'
ok "status eu" '[[ $($LP status | jq -r .region) == eu && $($LP status | jq -r .email) == me@example.com ]]'
$LP setup me@example.com us
ok "switch back to us unsets base_url" '[[ $(jq -r .base_url $P/state/config.json) == null && $($LP status | jq -r .region) == us ]]'

: > $P/state/log; touch $P/state/wrongpw; $LP fill
ok "fill: wrong password cancels" '! grep -q "^rofi-rbw" $P/state/log'
rm $P/state/wrongpw; : > $P/state/log; $LP fill
ok "fill: unlocks then opens picker" 'grep -qx "rbw unlock" $P/state/log && grep -q "^rofi-rbw --selector rofi --selector-args -config $HOME/.config/rofi/compact.rasi" $P/state/log'
: > $P/state/log; $LP fill
ok "fill: already unlocked skips unlock" '! grep -qx "rbw unlock" $P/state/log && grep -q "^rofi-rbw" $P/state/log'
ok "status unlocked" '[[ $($LP status | jq -r .unlocked) == true ]]'
$LP lock; ok "lock" '[[ ! -f $P/state/unlocked ]]'
ok "lock when locked exits 0" '$LP lock'

D=$P/home/Downloads
printf 'name,url,username,password,note\na,b,c,d,e\n' > "$D/Chrome Passwords.csv"
printf 'Title,Url,Username,Password\n' > "$D/lastpass.CSV"
printf 'date,amount\n1,2\n' > "$D/bank.csv"
echo '{}' > "$D/bitwarden_export_2026.json"; echo '{}' > "$D/notes.json"; echo x > "$D/old.1pux"
mkdir -p "$D/sub"; printf 'url,PASSWORD\n' > "$D/sub/apple.csv"
mapfile -t found < <($LP exports | xargs -d '\n' -n1 basename | sort)
ok "exports found" '[[ "${found[*]}" == "Chrome Passwords.csv apple.csv bitwarden_export_2026.json lastpass.CSV old.1pux" ]]'
$LP clean-exports >/dev/null
ok "clean-exports removed them" '[[ -z $($LP exports) ]]'
ok "clean-exports kept others" '[[ -f $D/bank.csv && -f $D/notes.json ]]'
ok "clean-exports nothing left msg" '$LP clean-exports | grep -q "No exported"'
ok "bad command" '! $LP nope 2>/dev/null'
rm -f $P/bin/rofi-rbw.off; mv $P/bin/rofi-rbw $P/bin/rofi-rbw.off
ok "status not installed" '[[ $($LP status | jq -r .installed) == false ]]'
: > $P/state/log; ok "fill not installed fails" '! $LP fill'
mv $P/bin/rofi-rbw.off $P/bin/rofi-rbw
echo "failures: $fails"; exit $fails
