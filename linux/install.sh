#!/bin/bash
# Install the Steam Screenshot Bridge for the current user.
#
# Everything lands under $HOME -- no root, and nothing on the read-only SteamOS
# root filesystem, so a SteamOS update will not remove it.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/steam-screenshot-bridge"
UNITS="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/ks-shot"

echo "==> checking dependencies"
missing=()
for tool in xbindkeys xdotool xprop ffmpeg python3; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "missing: ${missing[*]}" >&2
  echo "on SteamOS these all ship in the base image; on other distros install them first." >&2
  exit 1
fi
python3 -c 'import gi; gi.require_version("Gio", "2.0")' 2>/dev/null \
  || echo "note: python-gobject not found -- the tray will not run (the hotkey still will)"

echo "==> installing to $DEST"
mkdir -p "$DEST" "$UNITS" "$CONFIG_DIR"
install -m 755 "$SRC/ks-shot" "$SRC/steamshot.py" "$SRC/ks-tray.py" "$SRC/xbindkeys-start.sh" "$DEST/"

if [ ! -f "$CONFIG_DIR/config.ini" ]; then
  install -m 644 "$SRC/config.ini.example" "$CONFIG_DIR/config.ini"
  echo "    wrote default config: $CONFIG_DIR/config.ini"
else
  echo "    keeping existing config: $CONFIG_DIR/config.ini"
fi

# The hotkey grabber reads ~/.xbindkeysrc; generate it from the config.
HOTKEYS=$(grep -E '^hotkey=' "$CONFIG_DIR/config.ini" | sed 's/^hotkey=//' || true)
[ -z "$HOTKEYS" ] && HOTKEYS="F10"
: > "$HOME/.xbindkeysrc"
while IFS= read -r key; do
  [ -z "$key" ] && continue
  printf '"%s"\n  %s\n\n' "$DEST/ks-shot" "$key" >> "$HOME/.xbindkeysrc"
done <<< "$HOTKEYS"
echo "    hotkey(s): $(echo "$HOTKEYS" | tr '\n' ' ')"

echo "==> installing user services"
install -m 644 "$SRC/systemd/xbindkeys.service" "$SRC/systemd/ks-tray.service" "$UNITS/"
systemctl --user daemon-reload
systemctl --user enable --now xbindkeys.service
systemctl --user enable --now ks-tray.service || echo "    tray failed to start (python-gobject missing?)"

echo
echo "Installed."
echo "  Map a controller button (or a key) to your hotkey in Steam's controller layout."
echo "  Screenshots land in the Steam library under the focused game's AppID."
echo "  Log: ~/.local/share/ks-shot.log"
