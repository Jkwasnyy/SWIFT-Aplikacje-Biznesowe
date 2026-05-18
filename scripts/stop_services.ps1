$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptDir
$pidsFile = Join-Path $scriptDir "pids.txt"
if (-not (Test-Path $pidsFile)) {
    Write-Output "No pids file found at $pidsFile"
    exit 0
}

Get-Content $pidsFile | ForEach-Object {
    $parts = $_ -split '\|'
    if ($parts.Length -ge 3) {
        $name = $parts[0]
        $processId = [int]$parts[2]
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Output "Stopped $name PID $processId"
        } catch {
            Write-Output "Failed to stop PID $($processId): $($_.Exception.Message)"
        }
    }
}

Remove-Item $pidsFile
Write-Output "All stopped. $pidsFile removed."

Set-Location $projectRoot
