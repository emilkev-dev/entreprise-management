<#
Rôle du fichier:
Automatise le démarrage/arrêt propre de l'application Flask sous Windows,
avec options clean start, debug et mode foreground/background.
#>

param(
    [switch]$DebugMode,
    [switch]$CheckOnly,
    [switch]$Foreground,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runFile = Join-Path $projectRoot "run.py"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python introuvable: $pythonExe"
}

if (-not (Test-Path $runFile)) {
    Write-Error "run.py introuvable: $runFile"
}

if ($CheckOnly) {
    Write-Host "OK - Environnement valide"
    Write-Host "Python: $pythonExe"
    Write-Host "Entrée: $runFile"
    exit 0
}

function Stop-ExistingEnterpriseInstances {
    param(
        [string]$ProjectRoot,
        [string]$LockFilePath
    )

    Write-Host "Nettoyage des anciennes instances..."
    try {
        $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue
        foreach ($proc in ($processes | Where-Object { $_.CommandLine })) {
            $cmd = [string]$proc.CommandLine
            if ($cmd -like "*$ProjectRoot*" -and $cmd -like "*run.py*") {
                try {
                    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                } catch {}
            }
        }
    } catch {}

    if (Test-Path $LockFilePath) {
        try {
            Remove-Item $LockFilePath -Force -ErrorAction SilentlyContinue
            Write-Host "Lock file supprimé: $LockFilePath"
        } catch {}
    }
}

if ($DebugMode) {
    $env:FLASK_DEBUG = "1"
    Write-Host "Lancement en mode DEBUG"
} else {
    $env:FLASK_DEBUG = "0"
    Write-Host "Lancement en mode NORMAL"
}

Set-Location $projectRoot

if ($Clean) {
    Stop-ExistingEnterpriseInstances -ProjectRoot $projectRoot -LockFilePath (Join-Path $projectRoot ".run.lock")
}

if ($Foreground) {
    Write-Host "Lancement au premier plan..."
    & $pythonExe $runFile
    exit $LASTEXITCODE
}

Write-Host "Lancement en arrière-plan (processus détaché)..."
$process = Start-Process -FilePath $pythonExe -ArgumentList @($runFile) -WorkingDirectory $projectRoot -PassThru
Write-Host "Serveur démarré. PID: $($process.Id)"
Write-Host "URL: http://127.0.0.1:5000"
Write-Host "Pour arrêter: Stop-Process -Id $($process.Id)"
exit 0
