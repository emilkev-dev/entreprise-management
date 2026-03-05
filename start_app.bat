@echo off
:: Rôle du fichier: Lance le script PowerShell de démarrage de l'application
:: avec options de mode (normal/debug) et console (bg/fg).
setlocal

set "PROJECT_DIR=%~dp0"
set "PS_SCRIPT=%PROJECT_DIR%scripts\start_app.ps1"

if not exist "%PS_SCRIPT%" (
  echo [ERREUR] Script PowerShell introuvable: %PS_SCRIPT%
  pause
  exit /b 1
)

set "DEBUG_ARG="
set "FG_ARG="
set "MODE_ARG=bg"

if /I "%1"=="debug" (
  set "DEBUG_ARG=-DebugMode"
  echo Lancement en mode DEBUG - clean start...
) else (
  echo Lancement en mode NORMAL - clean start...
)

if /I "%2"=="bg" (
  set "FG_ARG="
  set "MODE_ARG=bg"
)

if /I "%2"=="fg" (
  set "FG_ARG=-Foreground"
  set "MODE_ARG=fg"
)

if /I "%MODE_ARG%"=="fg" (
  echo Mode console: FOREGROUND
) else (
  echo Mode console: BACKGROUND
)

echo Execution via PowerShell script...
powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Clean %DEBUG_ARG% %FG_ARG%
set "EXIT_CODE=%ERRORLEVEL%"

endlocal
exit /b %EXIT_CODE%
