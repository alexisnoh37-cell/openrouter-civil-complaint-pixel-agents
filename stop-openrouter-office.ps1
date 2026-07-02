$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root '.openrouter-office.pids.json'

if (Test-Path -LiteralPath $pidFile) {
    $saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    foreach ($name in @('backend', 'pixel')) {
        $processId = $saved.$name
        if ($processId) {
            Stop-Process -Id $processId -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $pidFile -Force
}

Write-Host 'OpenRouter Pixel Agents office stopped.'
