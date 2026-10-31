# Lennox tests

Run from the repo root. Outputs (test homes, screenshots, logs) land here and
are git-ignored.

- `bash tests/sweep.sh`: everything: shellcheck, pyflakes, JSON, the Hyprland
  Lua config against a 0.57 mock (all variants), GTK CSS, version vs
  changelog, and every Lennox Settings page opened under Xvfb.
- `bash tests/run_island.sh`: the dynamic island, driven in-process with a
  fake MPRIS player (screenshots `tests/isl-*.png`).
- `bash tests/run_island_big.sh`, `bash tests/run_wi_big.sh`: huge album covers stay small.
- `bash tests/run_widgets_interact.sh`: desktop widgets and the dashboard.

Needs: xvfb-run, dbus-run-session, ImageMagick (`import`), lua5.4,
shellcheck, jq, rsync, python3.12 with PyGObject + GTK4 + libadwaita, and
pyflakes (`pip install pyflakes`, or point `PYFLAKES="/path/python -m pyflakes"`).
