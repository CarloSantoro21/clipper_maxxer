# Levanta la API (puerto 8000) y el dashboard (puerto 3000) en Windows.
# Uso: .\scripts\dev.ps1          → sólo en esta PC
#      .\scripts\dev.ps1 -Lan     → también accesible desde tu celular en la misma red Wi-Fi
param([switch]$Lan)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$HostAddr = "127.0.0.1"
$ApiUrl = "http://localhost:8000"
if ($Lan) {
  $HostAddr = "0.0.0.0"
  $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
  $ApiUrl = "http://${ip}:8000"
  Write-Host "Desde el celular abre: http://${ip}:3000"
}

if (-not (Test-Path "dashboard/node_modules")) { Push-Location dashboard; npm install; Pop-Location }

$api = Start-Process -FilePath "clipforge" -ArgumentList "serve", "--host", $HostAddr, "--port", "8000" -PassThru -NoNewWindow
try {
  Push-Location dashboard
  $env:NEXT_PUBLIC_API_URL = $ApiUrl
  npx next dev -H $HostAddr -p 3000
} finally {
  Pop-Location
  if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id }
}
