#Path to build to run
$project = Join-Path $PSScriptRoot "..\..\Build\pc\benchmark.exe"
$conf = Join-Path $PSScriptRoot "..\..\Assets\Resources\NgoResource.json"

Write-Host "Starting Unity instances..."

$p1 = Start-Process $project -ArgumentList @(
    "-batchmode",
    "--server",
    "--conf-file", $conf
) -PassThru

$p2 = Start-Process $project -PassThru

Write-Host "Waiting for both runs..."
$p1.WaitForExit()
$p2.WaitForExit()

if ($p1.ExitCode -ne 0 -or $p2.ExitCode -ne 0) {
    Write-Error "Tests failed"
    exit 1
}

Write-Host "All tests passed"