param(
    [string[]]$ProjectFolders = @("base","base_DOTS","base_GPU","photonFusion","ngo","fishNet","NetcodeEntities"),
    [string[]]$GodotProjectFolders = @("Godot_Benchmark","Godot_Network_Benchmark"),
    [string]$DestinationPath = (Join-Path $PSScriptRoot "builds"),
    [switch]$SkipGodot
)

$unity_path = "C:\Program Files\Unity\Hub\Editor\6000.3.7f1\Editor\Unity.exe"
# Editor/tools build required for --export-* (the export-templates-only runtime can't export).
$godot_path = "C:\Program Files (x86)\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe"

# `& $godot_path ...` blocks until the process it launches exits, but that
# process can itself leave a background Godot instance running (observed:
# GDExtension addons like godotopenxrvendors keep their .dll locked by a
# process that outlives the one PowerShell waited on). Without this, the
# next export in the loop can fail to load that .dll, or Test-Path below
# can run before the real export has finished writing its output.
function Wait-ForGodotExit {
    param([int]$TimeoutSeconds = 180)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $warned = $false
    while ((Get-Date) -lt $deadline) {
        $procs = Get-Process -Name "godot*" -ErrorAction SilentlyContinue
        if (-not $procs) { return }
        if (-not $warned) {
            Write-Host "Waiting for background Godot process(es) to exit (PID(s): $($procs.Id -join ', '))..."
            $warned = $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "WARNING: timed out after ${TimeoutSeconds}s waiting for Godot to exit -- the export result below may be unreliable."
}

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

if (-not $SkipGodot) {
    $preexisting = Get-Process -Name "godot*" -ErrorAction SilentlyContinue
    if ($preexisting) {
        Write-Host "WARNING: Godot is already running (PID(s): $($preexisting.Id -join ', ')). Close every Godot editor window before exporting -- a running instance can hold GDExtension .dll files locked and make the exports below fail."
    }

    foreach ($folder in $GodotProjectFolders) {
        $project_path = Join-Path $PSScriptRoot $folder

        # --- PC (Windows Desktop) EXPORT ---
        $pc_dest_dir = Join-Path $DestinationPath $folder
        if (!(Test-Path $pc_dest_dir)) {
            New-Item -ItemType Directory -Path $pc_dest_dir | Out-Null
        }
        $pc_output = Join-Path $pc_dest_dir "benchmark.exe"

        Write-Host "Exporting Windows Desktop for $project_path..."
        & $godot_path --headless --path $project_path --export-debug "Windows Desktop" $pc_output
        Wait-ForGodotExit

        if (Test-Path $pc_output) {
            Write-Host "Finished Windows Desktop export for $folder"
        } else {
            Write-Host "Windows Desktop export failed for $folder (check that the 'Windows Desktop' preset exists in export_presets.cfg and export templates are installed)"
        }

        # --- ANDROID EXPORT ---
        $android_dest_dir = Join-Path $DestinationPath ($folder + "_android")
        if (!(Test-Path $android_dest_dir)) {
            New-Item -ItemType Directory -Path $android_dest_dir | Out-Null
        }
        $android_output = Join-Path $android_dest_dir "benchmark.apk"

        Write-Host "Exporting Android for $project_path..."
        & $godot_path --headless --path $project_path --export-debug "Android" $android_output
        Wait-ForGodotExit

        if (Test-Path $android_output) {
            Write-Host "Finished Android export for $folder"
        } else {
            Write-Host "Android export failed for $folder (check the Android SDK/debug keystore is configured in Editor Settings, and that export templates are installed)"
        }
    }
}

Write-Host "All builds complete"