$ErrorActionPreference = 'SilentlyContinue'
Get-Process -Name 'SteamScreenshotBridge', 'Win11SteamF10' | Stop-Process
$startup = [Environment]::GetFolderPath('Startup')
Remove-Item -LiteralPath (Join-Path $startup 'Steam Screenshot Bridge.lnk')
Remove-Item -LiteralPath (Join-Path $startup 'Win11 Steam F10.lnk')
Write-Host 'Stopped and removed from startup.'
