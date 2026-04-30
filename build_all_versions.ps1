$project_folders = @("base","base_DOTS","base_GPU","ngo")
$unity_path = "C:\Program Files\Unity\Hub\Editor\6000.3.7f1\Editor\Unity.exe"
$build_path_output = Join-Path $PSScriptRoot "builds"

if (!(Test-Path $build_path_output)) {
    New-Item -ItemType Directory -Path $build_path_output | Out-Null
}

foreach ($folder in $project_folders) {
    $project_path = Join-Path $PSScriptRoot $folder

    # --- PC BUILD ---
    Write-Host "Building PC project in $project_path..."
    Start-Process $unity_path -ArgumentList @(
        "-batchmode",
        "-nographics",
        "-projectPath", $project_path,
        "-executeMethod", "BuildCommands.PerformBuildPC",
        "-quit"
    ) -Wait

    $build_path = Join-Path $project_path "Build\pc"
    $output_path = Join-Path $build_path_output $folder

    if (Test-Path $build_path) {
        if (Test-Path $output_path) {
            Remove-Item $output_path -Recurse -Force
        }
        Move-Item $build_path $output_path
        Write-Host "Finished PC build for $folder"
    } else {
        Write-Host "PC build failed for $folder"
    }

    # --- ANDROID BUILD ---
    Write-Host "Building Android project in $project_path..."
    Start-Process $unity_path -ArgumentList @(
        "-batchmode",
        "-nographics",
        "-projectPath", $project_path,
        "-executeMethod", "BuildCommands.PerformBuildAndroid",
        "-quit"
    ) -Wait

    $build_path = Join-Path $project_path "Build\android"
    $output_path = Join-Path $build_path_output ($folder + "_android")

    if (Test-Path $build_path) {
        if (Test-Path $output_path) {
            Remove-Item $output_path -Recurse -Force
        }
        Move-Item $build_path $output_path
        Write-Host "Finished Android build for $folder"
    } else {
        Write-Host "Android build failed for $folder"
    }
}

Write-Host "All builds complete"