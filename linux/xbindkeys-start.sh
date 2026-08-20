#!/bin/bash
# Steam Screenshot Bridge
# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. See the LICENSE file for details.

# Start xbindkeys against the current session's X authority.
#
# On a Wayland desktop (SteamOS desktop mode is KDE Plasma + kwin_wayland) the
# XWayland authority file is created per session with a random name, so it has
# to be discovered at start time rather than hard-coded.
export DISPLAY="${DISPLAY:-:0}"

for _ in $(seq 1 30); do
  XA=$(pgrep -a kwin_wayland | grep -oE "xwayland-xauthority [^ ]+" | head -1 | awk '{print $2}')
  [ -n "$XA" ] && break
  sleep 2
done
[ -n "$XA" ] && export XAUTHORITY="$XA"

exec xbindkeys -n
