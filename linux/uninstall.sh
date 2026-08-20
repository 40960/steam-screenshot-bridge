#!/bin/bash
# Steam Screenshot Bridge
# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. See the LICENSE file for details.

# Remove the Steam Screenshot Bridge for the current user.
# Screenshots already in the Steam library are untouched.
set -uo pipefail

DEST="$HOME/.local/share/steam-screenshot-bridge"
UNITS="$HOME/.config/systemd/user"

echo "==> stopping services"
systemctl --user disable --now ks-tray.service 2>/dev/null
systemctl --user disable --now xbindkeys.service 2>/dev/null
rm -f "$UNITS/ks-tray.service" "$UNITS/xbindkeys.service"
systemctl --user daemon-reload 2>/dev/null

echo "==> removing files"
rm -rf "$DEST"
rm -f "$HOME/.xbindkeysrc"

echo
echo "Removed. Kept on purpose:"
echo "  ~/.config/ks-shot/config.ini   (your hotkey setting)"
echo "  ~/.local/share/ks-shot.log     (log)"
echo "  /tmp/ks-shot/                  (temporary captures, cleared by the OS)"
