# shellcheck shell=bash disable=SC2034
# The Lennox terminal look. Sourced by install.sh and by `lennox upgrade` (lennox-update-dotfiles).
#   ui_init                       colors on only in a real terminal (never in logs or pipes; NO_COLOR turns them off)
#   ui_banner TITLE [SUB]         a boxed header
#   step TITLE | ok | note | warn | die
#   ui_done TITLE                 the closing box: how long it took, and any warnings
#   ui_duration SECONDS           "1m 12s"
#   ui_strip                      a filter that removes the colors (for the log file)
# All text inside a box is plain ASCII so the box lines up in any terminal.

UI_WIDTH=54
UI_T0=$SECONDS
UI_STEP_T0=$SECONDS
UI_STEP_OPEN=0
UI_TTY=false

ui_init() {
    UI_TTY=false
    [[ -t 1 && "${TERM:-dumb}" != dumb ]] && UI_TTY=true      # decided before any output goes through tee
    local on=false
    if [[ -n "${LENNOX_COLOR:-}" ]]; then on=true
    elif [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != dumb ]]; then on=true; fi
    if $on; then
        reset=$'\e[0m'; bold=$'\e[1m'; dim=$'\e[2m'
        if [[ "${COLORTERM:-}" == truecolor || "${COLORTERM:-}" == 24bit || -n "${LENNOX_COLOR:-}" ]]; then
            accent=$'\e[38;2;122;162;255m'; violet=$'\e[38;2;167;139;250m'; gold=$'\e[38;2;255;210;122m'
            green=$'\e[38;2;120;220;160m'; yellow=$'\e[38;2;255;200;100m'; red=$'\e[38;2;255;120;130m'; cyan=$accent
        else
            accent=$'\e[36m'; violet=$'\e[35m'; gold=$'\e[33m'; green=$'\e[32m'; yellow=$'\e[33m'; red=$'\e[31m'; cyan=$'\e[36m'
        fi
    else
        reset=""; bold=""; dim=""; accent=""; violet=""; gold=""; green=""; yellow=""; red=""; cyan=""
    fi
}

ui_duration() {
    local s="$1"
    if (( s >= 3600 )); then printf '%dh %02dm' $((s / 3600)) $((s % 3600 / 60))
    elif (( s >= 60 )); then printf '%dm %02ds' $((s / 60)) $((s % 60))
    else printf '%ds' "$s"; fi
}

ui_strip() { sed -u $'s/\e\\[[0-9;]*m//g'; }

# A line inside the box: |  text.....  |  (text is ASCII, padded to the box width)
ui_boxline() {   # ui_boxline COLOR TEXT
    local color="$1" text="$2" pad
    pad=$(( UI_WIDTH - 6 - ${#text} ))
    (( pad < 0 )) && { text="${text:0:$((UI_WIDTH - 9))}..."; pad=0; }
    printf '  %s│%s  %s%s%s%*s  %s│%s\n' "$accent" "$reset" "$color" "$text" "$reset" "$pad" "" "$accent" "$reset"
}

ui_rule() {   # ui_rule LEFT RIGHT
    local line; printf -v line '%*s' $((UI_WIDTH - 2)) ''; line="${line// /─}"
    printf '  %s%s%s%s%s\n' "$accent" "$1" "$line" "$2" "$reset"
}

ui_banner() {   # ui_banner TITLE [SUB]
    echo
    ui_rule "╭" "╮"
    ui_boxline "${bold}${gold}" "* LENNOX   $1"
    [[ -n "${2:-}" ]] && ui_boxline "$dim" "$2"
    ui_rule "╰" "╯"
}

ui_close_step() {
    if (( UI_STEP_OPEN )); then
        local took=$(( SECONDS - UI_STEP_T0 ))
        (( took >= 3 )) && echo "    ${dim}took $(ui_duration "$took")${reset}"
    fi
    UI_STEP_OPEN=0
}

step() { ui_close_step; UI_STEP_T0=$SECONDS; UI_STEP_OPEN=1; echo; echo "  ${accent}${bold}◆${reset} ${bold}$*${reset}"; }
ok()   { echo "    ${green}✓${reset} $*"; }
note() { echo "    ${dim}$*${reset}"; }
warn() { echo "    ${yellow}▲${reset} $*"; WARNINGS+=("$*"); }
die()  {
    ui_close_step
    echo; echo "  ${red}${bold}✗ $*${reset}"
    [[ -n "${LOGFILE:-}" ]] && echo "    ${dim}Full log: $LOGFILE${reset}"
    exit 1
}

ui_done() {   # ui_done TITLE
    ui_close_step
    local took; took="$(ui_duration $(( SECONDS - UI_T0 )))"
    echo
    ui_rule "╭" "╮"
    ui_boxline "${bold}${green}" "OK  $1"
    ui_boxline "$dim" "took $took"
    ui_rule "╰" "╯"
    if (( ${#WARNINGS[@]} )); then
        echo
        echo "  ${yellow}${bold}A few things to look at:${reset}"
        local w
        for w in "${WARNINGS[@]}"; do echo "    ${yellow}▲${reset} $w"; done
    fi
}

# A spinner for a slow command:  ui_spin "Installing cava" sudo pacman -S --needed --noconfirm cava
# In a terminal: an animated line (drawn on the terminal itself, never into the log) with the time it has taken.
# Without one: a plain "..." line. The command's output goes to the log, not the screen; if it fails, its last
# lines are shown. The command runs in the background, so use it for commands that need no typing (run
# sudo -v first for a password), and for effects (installing, building), not for setting variables.
# Returns the command's exit code; the caller prints the result line (ok / warn).
ui_spin() {
    local msg="$1"; shift
    local out t0=$SECONDS code pid i=0
    out="$(mktemp)"
    local -a frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    "$@" >"$out" 2>&1 </dev/null &
    pid=$!
    if $UI_TTY && [[ -w /dev/tty ]]; then
        while kill -0 "$pid" 2>/dev/null; do
            printf '\r    %s%s%s %s %s(%s)%s\033[K' "$accent" "${frames[i % 10]}" "$reset" "$msg" "$dim" "$(ui_duration $((SECONDS - t0)))" "$reset" >/dev/tty
            i=$((i + 1)); sleep 0.1
        done
        printf '\r\033[K' >/dev/tty
    else
        echo "    ${dim}… $msg${reset}"
    fi
    wait "$pid"; code=$?
    if [[ -n "${LOGFILE:-}" ]]; then { echo "== $msg"; cat "$out"; } | ui_strip >> "$LOGFILE"; fi
    if (( code != 0 )); then
        echo "    ${red}✗${reset} $msg ${dim}(failed, the last lines:)${reset}"
        tail -n 12 "$out" | sed "s/^/      ${dim}/; s/\$/${reset}/"
    fi
    rm -f "$out"
    return "$code"
}
