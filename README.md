# Steam Screenshot Bridge

Steam screenshots for games that can't have them.

Some games have **`DisableOverlay = 1`** set in their Steam app metadata by the
publisher. Steam then never starts the overlay UI process for them, so `F12` and
`Shift+Tab` do nothing — permanently, on any machine, with no setting to change.
The renderer is injected and healthy; it just waits forever for an overlay UI
that is never launched.

This project takes the screenshot itself and registers it through
`ISteamScreenshots::AddScreenshotToLibrary`, a separate code path that
`DisableOverlay` does not block. The screenshot ends up in the real Steam
library under the correct AppID, with a thumbnail, and can be viewed and shared
like any other.

Nothing here modifies, injects into, or restarts Steam or the game.

## Platforms

| | |
|---|---|
| [`linux/`](linux/) | SteamOS / KDE Plasma. Tested on ROG Ally X running SteamOS desktop mode. |
| [`windows/`](windows/) | Windows 11. C# / WinForms tray helper, same approach. |

## How to tell if this is your problem

The game's overlay is disabled by its own metadata if:

- `F12` and `Shift+Tab` do nothing in desktop mode, for that game only
- screenshots still work in Steam Deck Gaming Mode (that path goes through
  gamescope's compositor and does not use the overlay UI)
- SteamDB shows `DisableOverlay: Yes` for the AppID

On Linux you can confirm it directly:

```bash
# never logs a line for the affected AppID, but does for every other game
grep "GameOverlay: started" ~/.local/share/Steam/logs/console_log.txt

# with STEAM_OVERLAY_LOGGING=1, the renderer log repeats this forever:
#   Disabling overlay for 2 seconds (N seconds since last frame from ui process was seen)
```

## Not a fix for the overlay

The Steam Overlay stays disabled for these games — only the publisher can clear
that flag. This restores the screenshots, not the overlay.

## License

GNU Affero General Public License v3.0 or later. See [LICENSE](LICENSE).
