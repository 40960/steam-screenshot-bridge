# Steam Screenshot Bridge — Linux (SteamOS / KDE Plasma)

Gets Steam screenshots working for games that have **DisableOverlay** set in
their Steam app metadata, where `F12` and `Shift+Tab` do nothing and never will.

Tested on SteamOS desktop mode (KDE Plasma 6 + `kwin_wayland`) on ROG Ally X.

## What it does

```
controller back button (Steam Input sends e.g. F10)
  → xbindkeys           grabs the key
  → ks-shot             captures the focused game window with ffmpeg,
                        reads the AppID from the window's steam_app_<id> class
  → steamshot.py        registers it with ISteamScreenshots::AddScreenshotToLibrary
  → Steam               copies it in, makes the thumbnail, writes screenshots.vdf,
                        links it to the current game session timeline
```

The result is a normal library screenshot: correct game, viewable and shareable
from Steam like any other. Achievements, cloud saves and playtime are untouched,
and Steam itself is never modified, injected into or restarted.

## Install

```bash
./install.sh
```

Then map a controller button to the hotkey in **Steam → the game → controller
layout → button → Keyboard → F10**. Leave your normal screenshot button alone;
it still works in Gaming Mode.

Uninstall with `./uninstall.sh`.

## Changing the hotkey

Tray menu → **打开配置** (open configuration) → edit `hotkey=` → save → tray menu
→ **重新加载热键** (reload hotkey). Or edit `~/.config/ks-shot/config.ini` and run
`systemctl --user restart xbindkeys.service`.

### One caveat worth knowing

On a Wayland desktop, kwin delivers most **plain** keys straight to the focused
window, so an X-level grabber may not see them. In practice:

- a plain key (`F10`) **is** caught when Steam Input injects it from a controller
- the same key pressed on a **physical keyboard** may not be caught
- a `Control+Alt+…` combination is caught in both cases

So use a plain key for a controller button, and a Control+Alt combination if you
also want a keyboard shortcut.

## Files

| Path | |
|---|---|
| `~/.local/share/steam-screenshot-bridge/` | the scripts |
| `~/.config/ks-shot/config.ini` | hotkey setting |
| `~/.xbindkeysrc` | generated from the config |
| `~/.local/share/ks-shot.log` | log |
| `~/.config/systemd/user/xbindkeys.service` | the hotkey grabber |
| `~/.config/systemd/user/ks-tray.service` | the tray |

The tray only observes and controls `xbindkeys.service`; it deliberately does
not run its own grabber, because two grabbers fight over the same key.

## Requirements

Everything ships in the SteamOS base image, which matters: SteamOS updates
replace the read-only root filesystem, so anything installed with `pacman` would
be wiped.

`xbindkeys`, `xdotool`, `xprop`, `ffmpeg`, `python3`, `python-gobject` (tray only).

## Tray

Native StatusNotifierItem + `com.canonical.dbusmenu`, which is what Plasma speaks
directly. Going through `Gtk.StatusIcon` and `xembedsniproxy` shows the icon but
loses the menu, so the D-Bus interfaces are implemented by hand.

Menu: status line · 立即截图 · 打开配置 · 重新加载热键 · 查看日志 · 退出
