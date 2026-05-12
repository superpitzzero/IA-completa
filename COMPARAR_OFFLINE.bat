@echo off
setlocal enabledelayedexpansion

REM Comparativa offline (sin APIs): model cards + rendimiento local
REM Salida: logs\comparativas\comparativa_offline_*.{md,html,json}

set ROOT=%~dp0
cd /d "%ROOT%"

if not exist "logs\comparativas" (
  mkdir "logs\comparativas" >NUL 2>&1
)

set TS=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TS=%TS: =0%

set OUTDIR=logs\comparativas

echo Ejecutando comparativa_offline.py ...
python "comparativa_offline.py" --out-dir "%OUTDIR%" %*
set ERR=%ERRORLEVEL%

if not "%ERR%"=="0" (
  echo ERROR: comparativa_offline.py fallo con exit code %ERR%
  exit /b %ERR%
)

echo OK. Archivos guardados en "%OUTDIR%".
exit /b 0

