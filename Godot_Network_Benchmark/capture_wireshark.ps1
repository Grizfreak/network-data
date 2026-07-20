param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop")]
    [string]$Action,

    [string]$OutputFile = "capture.pcap",

    [string]$Filter = "udp",

    [string]$Interface = "Wi-Fi"
)

$PidFile = Join-Path $PSScriptRoot "tshark.pid"

switch ($Action)
{
    "start"
    {
        if (Test-Path $PidFile)
        {
            $OldPid = Get-Content $PidFile

            try
            {
                $Existing = Get-Process -Id $OldPid -ErrorAction Stop
                Write-Host "tshark is already running (PID $OldPid)."
                exit 1
            }
            catch
            {
                Remove-Item $PidFile -Force
            }
        }

        $Arguments = "-i `"$Interface`" -w `"$OutputFile`" -f `"$Filter`""

        Write-Host "Arguments:"
        Write-Host $Arguments
        try {
        $Process = Start-Process `
            -FilePath "tshark.exe" `
            -ArgumentList $Arguments `
            -WindowStyle Hidden `
            -PassThru `
            -ErrorAction Stop

        $Process.Id | Set-Content $PidFile

        Write-Host "Started tshark (PID $($Process.Id))"
        }
        catch {
            Write-Host $.Exception.Message
            exit 1
        }
    }

    "stop"
    {
        if (!(Test-Path $PidFile))
        {
            Write-Host "No PID file found."
            exit 0
        }

        $ProcessId = Get-Content $PidFile

        try
        {
            Stop-Process -Id $ProcessId -Force
            Write-Host "Stopped tshark (PID $ProcessId)"
        }
        catch
        {
            Write-Host "Process already exited."
        }

        Remove-Item $PidFile -Force
    }
}