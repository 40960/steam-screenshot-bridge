$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# A release download has the exe next to this script; a source build leaves it
# in the publish folder.
$exe = Join-Path $root 'SteamScreenshotBridge.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    $exe = Join-Path $root 'bin\Release\net8.0-windows\win-x64\publish\SteamScreenshotBridge.exe'
}
if (-not (Test-Path -LiteralPath $exe)) { throw "SteamScreenshotBridge.exe not found: build it, or run this next to the exe" }
$startup = [Environment]::GetFolderPath('Startup')
$shortcut = Join-Path $startup 'Steam Screenshot Bridge.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $exe
$link.WorkingDirectory = Split-Path -Parent $exe
$link.WindowStyle = 7
$link.IconLocation = "$exe,0"
$link.Save()
Start-Process -FilePath $exe -WindowStyle Hidden
Write-Host 'Installed. Steam Screenshot Bridge is now running for installed Steam games.'
