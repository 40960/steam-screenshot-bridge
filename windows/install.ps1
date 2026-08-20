$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root 'bin\Release\net8.0-windows\win-x64\publish\SteamScreenshotBridge.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Build not found: $exe" }
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
