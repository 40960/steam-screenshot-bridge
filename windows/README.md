# Steam Screenshot Bridge — Windows 11

Gets Steam screenshots working for games that have **DisableOverlay** set in
their Steam app metadata, where `F12` and `Shift+Tab` do nothing and never will.

## What it does

```
hotkey (default F10)
  → global RegisterHotKey    observed, never swallowed or rewritten
  → foreground window check  the executable must live inside a known Steam
                             game's install folder
  → appmanifest_*.acf        the matching manifest supplies the AppID
  → client-area capture      saved as JPEG
  → ISteamScreenshots        AddScreenshotToLibrary
```

Every Steam library folder is scanned, so the AppID is resolved automatically
and screenshots are filed under the right game. It never injects into, closes,
restarts or modifies Steam or the game.

## Build

Requires the .NET 8 SDK.

```powershell
dotnet publish -c Release
```

Produces `bin\Release\net8.0-windows\win-x64\publish\SteamScreenshotBridge.exe`,
which is what `install.ps1` looks for.

Building from macOS or Linux works too (you just cannot run the result) — add
`-p:EnableWindowsTargeting=true`.

### steam_api64.dll

Steam for Windows does not ship `steam_api64.dll` itself — it is the Steamworks
redistributable that games bundle. The bridge finds one automatically by
scanning your installed Steam games the first time it registers a screenshot.

If you would rather not have it search (or you hit an unusual setup), copy
`steam_api64.dll` out of any installed Steam game into the folder next to
`SteamScreenshotBridge.exe`; that copy wins and no search happens.

## Install

Finish and save whatever you are playing first — the helper is deliberately not
auto-started while a game is active.

```powershell
.\install.ps1
```

That creates a per-user startup shortcut and launches the silent helper. A tray
icon appears with the current hotkey; its menu opens the configuration or exits.

```powershell
.\uninstall.ps1
```

stops it and removes the startup shortcut.

## Changing the hotkey

Tray menu → **Open configuration** → edit the `hotkey=` line → save → restart the
bridge. `config.ini` lists every accepted key and modifier name.

```ini
hotkey=F10
; hotkey=PrintScreen
; hotkey=Ctrl+Shift+S
```

## Files

| | |
|---|---|
| `Program.cs` | the whole helper: hotkey, tray, capture, Steam registration |
| `config.ini` | hotkey setting, with the full list of valid key names |
| `install.ps1` / `uninstall.ps1` | startup shortcut management |
| `steam-f10.ico` | application/tray icon |

Runtime data (log, config copy) lives under the per-user application data
directory; nothing is written outside your profile.
