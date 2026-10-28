#            _
#    _______| |__  _ __ ___
#   |_  / __| '_ \| '__/ __|
#  _ / /\__ \ | | | | | (__
# (_)___|___/_| |_|_|  \___|
#
# Lennox zsh loader (same layout as ML4W): every file in ~/.config/zshrc
# is loaded in order. Put your own things in ~/.config/zshrc/90-custom;
# Lennox updates never touch that file.

for f in "$HOME"/.config/zshrc/*(N); do
    [[ -r "$f" ]] && source "$f"
done
