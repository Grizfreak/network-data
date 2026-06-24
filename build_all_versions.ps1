param(
    [string[]]$ProjectFolders = @("base","base_DOTS","base_GPU","photonFusion","ngo","fishNet","NetcodeEntities"),
    [string]$DestinationPath = (Join-Path $PSScriptRoot "builds")
)

$unity_path = "C:\Program Files\Unity\Hub\Editor\6000.3.7f1\Editor\Unity.exe"

if (!(Test-Path $DestinationPath)) {
    New-Item -ItemType Directory -Path $DestinationPath | Out-Null
}

foreach ($folder in $ProjectFolders) {
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
    if (Test-Path $DestinationPath) {
        Remove-Item (Join-Path $DestinationPath $folder) -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        New-Item -ItemType Directory -Path (Join-Path $DestinationPath $folder) | Out-Null
    }
    
    if (!(Test-Path $build_path)) {
        Write-Host "PC build failed for $folder"
        continue
    }

    Move-Item $build_path (Join-Path $DestinationPath $folder) -Force
    
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
    
    # Create destination directory if needed for Android builds (with _android suffix)
    $androidDestDir = Join-Path $DestinationPath ($folder + "_android")
    if (!(Test-Path $androidDestDir)) {
        New-Item -ItemType Directory -Path $androidDestDir | Out-Null
    }

    if (Test-Path $build_path) {
        Move-Item $build_path $androidDestDir -Force
        Write-Host "Finished Android build for $folder"
    } else {
        Write-Host "Android build failed for $folder"
    }
}

Write-Host "All builds complete"