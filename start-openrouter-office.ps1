$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'civil-backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$cli = Join-Path $root 'dist\cli.js'
$pidFile = Join-Path $root '.openrouter-office.pids.json'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $cli)) {
    throw 'Setup is incomplete. Run .\setup.ps1 first.'
}

function Test-Port([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

$processes = @{}
if (-not (Test-Port 8000)) {
    $backendProcess = Start-Process -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru
    $processes.backend = $backendProcess.Id
}

if (-not (Test-Port 3100)) {
    $pixelProcess = Start-Process -FilePath 'node.exe' `
        -ArgumentList @($cli, '--host', '127.0.0.1', '--port', '3100') `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $processes.pixel = $pixelProcess.Id
}

$processes | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-Port 8000) -and (Test-Port 3100)) { break }
    Start-Sleep -Milliseconds 500
}

if (-not ((Test-Port 8000) -and (Test-Port 3100))) {
    throw 'Servers did not start. Check whether ports 8000 and 3100 are available.'
}

Start-Process 'http://127.0.0.1:3100'
Write-Host 'OpenRouter Pixel Agents office: http://127.0.0.1:3100'
Write-Host 'Civil complaint API:          http://127.0.0.1:8000'
