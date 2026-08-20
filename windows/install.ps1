$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# A release download has the exe next to this script; a source build leaves it
# in the publish folder.
$exe = Join-Path $root 'SteamScreenshotBridge.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    $exe = Join-Path $root 'bin\Release\net8.0-windows\win-x64\publish\SteamScreenshotBridge.exe'
}
if (-not (Test-Path -LiteralPath $exe)) { throw "SteamScreenshotBridge.exe not found: build it, or run this next to the exe" }
# This folder is the install location: the startup shortcut points straight at
# this exe, so do not extract to a temporary folder and delete it afterwards.
Write-Host "Installing from: $(Split-Path -Parent $exe)"

# Upgrading over an older copy: stop it first. The program is single-instance,
# so a leftover process would keep the new one from starting at all.
$old = Get-Process -Name 'SteamScreenshotBridge' -ErrorAction SilentlyContinue
if ($old) {
    Write-Host 'Stopping the running copy first...'
    $old | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

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
