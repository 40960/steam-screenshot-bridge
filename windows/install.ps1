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

# A framework-dependent build exits immediately when the .NET Desktop Runtime is
# missing, so confirm it is actually running instead of claiming success.
Start-Sleep -Seconds 3
$running = Get-Process -Name 'SteamScreenshotBridge' -ErrorAction SilentlyContinue
if ($running) {
    Write-Host 'Installed. Steam Screenshot Bridge is running; look for the tray icon.'
    Write-Host 'It will start automatically when you log in.'
}
else {
    Write-Warning 'The bridge was installed but is not running.'
    Write-Host ''
    Write-Host 'The usual cause is a missing runtime for this (framework-dependent) build.'
    Write-Host 'Either install the .NET 8 Desktop Runtime (x64):'
    Write-Host '  https://dotnet.microsoft.com/download/dotnet/8.0'
    Write-Host 'or download the self-contained build instead, which needs no runtime.'
    Write-Host ''
    Write-Host 'To see the actual error, run the exe directly from this window:'
    Write-Host "  & '$exe'"
}
