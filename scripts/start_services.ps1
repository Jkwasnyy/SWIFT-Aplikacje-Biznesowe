param(
    [int[]] $Ports = @(3001,3002,3003,3004,3005,3006,3007,3008)
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptDir
$pidsFile = Join-Path $scriptDir "pids.txt"

Set-Location $projectRoot

if (Test-Path $pidsFile) { Remove-Item $pidsFile }

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    $pythonExe = "py"
    $pythonArgs = "-3"
} else {
    $pythonExe = "python"
    $pythonArgs = ""
}

Write-Output "Starting mock banks on ports: $($Ports -join ', ')"
foreach ($port in $Ports) {
    $args = @()
    if ($pythonArgs) { $args += $pythonArgs }
    $args += (Join-Path $projectRoot "mocks\mock_bank.py")
    $args += $port
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $args -WorkingDirectory $projectRoot -WindowStyle Normal -PassThru
    "mock_bank|$port|$($proc.Id)" | Out-File -FilePath $pidsFile -Append -Encoding utf8
    Start-Sleep -Milliseconds 200
}

Write-Output "Starting main app"
$appArgs = @()
if ($pythonArgs) { $appArgs += $pythonArgs }
$appArgs += "-m"
$appArgs += "app.main"
$appProc = Start-Process -FilePath $pythonExe -ArgumentList $appArgs -WorkingDirectory $projectRoot -WindowStyle Normal -PassThru
"app_main|app|$($appProc.Id)" | Out-File -FilePath $pidsFile -Append -Encoding utf8

Write-Output "Started processes. PIDs saved to $pidsFile"
Write-Output "To stop all services run: .\scripts\stop_services.ps1"
