$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'civil-backend'
$venvPython = Join-Path $backend '.venv\Scripts\python.exe'

Push-Location $root
try {
    $env:PUPPETEER_SKIP_DOWNLOAD = 'true'
    npm install
    npm run build:webview
    node esbuild.js --production
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        & py -3 -m venv (Join-Path $backend '.venv')
    } else {
        & python -m venv (Join-Path $backend '.venv')
    }
}

& $venvPython -m pip install -r (Join-Path $backend 'requirements.txt')

if (-not (Test-Path -LiteralPath (Join-Path $backend '.env'))) {
    Copy-Item -LiteralPath (Join-Path $backend '.env.example') -Destination (Join-Path $backend '.env')
    Write-Host 'Created civil-backend/.env. Add your OPENROUTER_API_KEY before running.'
}

Write-Host 'Setup complete.'
