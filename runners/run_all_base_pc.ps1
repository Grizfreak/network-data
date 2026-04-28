#$projects = @("base","base_DOTS","base_GPU");
$projects = @("base_DOTS","base_GPU");
$conf_file = Join-Path $PSScriptRoot "..\Resources\1Million.json"

foreach ($project in $projects) {
    $build_path = Join-Path $PSScriptRoot "..\builds\$project\benchmark.exe"
    Write-Host "Running benchmark for $project..."
    Start-Process $build_path -ArgumentList @(
        "--conf-file", $conf_file
    ) -Wait
}