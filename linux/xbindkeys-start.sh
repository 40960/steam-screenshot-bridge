#!/bin/bash
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
