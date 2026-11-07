#!/usr/bin/env bash
# `lennox upgrade` against a fake repository: the header, the list of changes, and the hand-over to the installer.
# Run: bash tests/test_upgrade_look.sh
SP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$SP/.." && pwd)"
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
T="$(mktemp -d)"; export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
git init -q --bare "$T/origin.git"
git clone -q "$T/origin.git" "$T/work" 2>/dev/null
mkdir -p "$T/work/setup/lib" "$T/work/dotfiles/.local/share/lennox/python/lennox"
cp "$R/setup/lib/ui.sh" "$T/work/setup/lib/"
printf '#!/usr/bin/env bash\necho "STUB install.sh $* banner_done=${LENNOX_BANNER_DONE:-no}"\n' > "$T/work/install.sh"; chmod +x "$T/work/install.sh"
printf 'VERSION = "1.0.0"\n' > "$T/work/dotfiles/.local/share/lennox/python/lennox/__init__.py"
(cd "$T/work" && git add -A && git commit -q -m "First" && git push -q origin HEAD:main 2>/dev/null)
H="$T/home"; mkdir -p "$H/.config/lennox"
git clone -q -b main "$T/origin.git" "$H/lennox-repo" 2>/dev/null
echo "$H/lennox-repo" > "$H/.config/lennox/repo"; echo "1.0.0" > "$H/.config/lennox/version"
for n in "Faster boot menu" "Simple sound" "Power mode by itself"; do
    (cd "$T/work" && echo "$n" >> notes.txt && git add -A && git commit -q -m "$n")
done
(cd "$T/work" && printf 'VERSION = "1.1.0"\n' > dotfiles/.local/share/lennox/python/lennox/__init__.py && git add -A && git commit -q -m "Bump to 1.1.0" && git push -q origin HEAD:main 2>/dev/null)

OUT="$(HOME=$H bash "$R/dotfiles/.local/bin/lennox-update-dotfiles" 2>&1)"
check "the header names the upgrade and both versions" "grep -q 'LENNOX   upgrade' <<<\"\$OUT\" && grep -q '1.0.0 -> 1.1.0' <<<\"\$OUT\""
check "it counts the new changes" "grep -q '4 new changes' <<<\"\$OUT\""
check "it lists them, newest first" "grep -q 'Bump to 1.1.0' <<<\"\$OUT\" && grep -q 'Simple sound' <<<\"\$OUT\" && grep -q 'Faster boot menu' <<<\"\$OUT\""
check "the installer gets --update and knows the header was shown" "grep -q 'STUB install.sh --update banner_done=1' <<<\"\$OUT\""
check "no color codes in a pipe" "! grep -q \$'\\e' <<<\"\$OUT\""

OUT2="$(HOME=$H bash "$R/dotfiles/.local/bin/lennox-update-dotfiles" 2>&1)"
check "nothing new: says so, still refreshes" "grep -q 'Already the latest' <<<\"\$OUT2\" && grep -q 'STUB install.sh --update' <<<\"\$OUT2\""

echo "local edit" >> "$H/lennox-repo/notes.txt"; (cd "$H/lennox-repo" && git add -A && git commit -q -m "local")
(cd "$T/work" && git pull -q --rebase origin main 2>/dev/null; echo more >> other.txt && git add -A && git commit -q -m "remote" && git push -q origin HEAD:main 2>/dev/null)
OUT3="$(HOME=$H bash "$R/dotfiles/.local/bin/lennox-update-dotfiles" 2>&1)"; code=$?
check "a diverged repository: stops with a message, does not run the installer" "[ $code -ne 0 ] && grep -q 'git pull failed' <<<\"\$OUT3\" && ! grep -q 'STUB install' <<<\"\$OUT3\""

echo "" > "$H/.config/lennox/repo"
OUT4="$(HOME=$H bash "$R/dotfiles/.local/bin/lennox-update-dotfiles" 2>&1)"
check "no repository known: says how to fix it" "grep -q \"Can't find the Lennox repository\" <<<\"\$OUT4\""
rm -rf "$T"; exit $fail
