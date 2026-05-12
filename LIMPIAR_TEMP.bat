@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

if not exist "logs" mkdir "logs" >nul 2>nul

for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format \"yyyyMMdd_HHmmss\""' ) do set "TS=%%I"
set "LOG_FILE=%~dp0logs\limpiar_temp_%TS%.log"

set "DAYS_LOGS=14"
set "DAYS_UPLOADS=14"

echo ============================================================>>"%LOG_FILE%"
echo LIMPIAR_TEMP - %DATE% %TIME%>>"%LOG_FILE%"
echo ROOT: %~dp0>>"%LOG_FILE%"
echo LOG:  %LOG_FILE%>>"%LOG_FILE%"
echo Retencion logs: %DAYS_LOGS% dias>>"%LOG_FILE%"
echo Retencion uploads: %DAYS_UPLOADS% dias>>"%LOG_FILE%"
echo ============================================================>>"%LOG_FILE%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$root = [IO.Path]::GetFullPath('%~dp0');" ^
  "$log = '%LOG_FILE%';" ^
  "$daysLogs = [int]%DAYS_LOGS%; $daysUploads = [int]%DAYS_UPLOADS%;" ^
  "function Log([string]$m){ Add-Content -LiteralPath $log -Value ('['+(Get-Date -Format 'HH:mm:ss')+'] '+$m) -Encoding UTF8 }" ^
  "function SafeRemovePath([string]$path){ if(Test-Path -LiteralPath $path){ Log ('Borrando: '+$path); Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue } }" ^
  "function SafeRemoveFilesOlderThan([string]$dir,[string]$pattern,[int]$days){" ^
  "  if(-not (Test-Path -LiteralPath $dir)) { return }" ^
  "  $cut = (Get-Date).AddDays(-$days);" ^
  "  Get-ChildItem -LiteralPath $dir -File -Filter $pattern -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } | ForEach-Object { Log ('Borrando: '+$_.FullName); Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }" ^
  "}" ^
  "" ^
  "Log 'Limpieza segura (lista blanca) iniciada.';" ^
  "" ^
  "# 1) Cache/bytecode Python y ruff" ^
  "SafeRemovePath (Join-Path $root '__pycache__');" ^
  "Get-ChildItem -LiteralPath $root -Directory -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq '__pycache__' } | ForEach-Object { SafeRemovePath $_.FullName }" ^
  "Get-ChildItem -LiteralPath $root -File -Recurse -Force -ErrorAction SilentlyContinue -Include *.pyc,*.pyo | ForEach-Object { Log ('Borrando: '+$_.FullName); Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }" ^
  "SafeRemovePath (Join-Path $root '.ruff_cache');" ^
  "" ^
  "# 2) Restos de descargas temporales de tools/ (cloudflared.download, *.download)" ^
  "SafeRemoveFilesOlderThan (Join-Path $root 'tools') '*.download' 0;" ^
  "" ^
  "# 3) Rotación/limpieza de logs viejos" ^
  "$logsDir = Join-Path $root 'logs';" ^
  "SafeRemoveFilesOlderThan $logsDir '*.log' $daysLogs;" ^
  "" ^
  "# 4) Logs sueltos en la raiz (ej: debug-*.log) - solo si son .log" ^
  "SafeRemoveFilesOlderThan $root 'debug-*.log' $daysLogs;" ^
  "" ^
  "# 5) Uploads web antiguos (solo archivos; NO borra settings/chats/memory/users)" ^
  "$uploads = Join-Path $root 'web_data\\uploads';" ^
  "if(Test-Path -LiteralPath $uploads){" ^
  "  $cut = (Get-Date).AddDays(-$daysUploads);" ^
  "  Get-ChildItem -LiteralPath $uploads -File -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } | ForEach-Object { Log ('Borrando upload viejo: '+$_.FullName); Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }" ^
  "}" ^
  "" ^
  "Log 'Listo.';"

echo.
echo [OK] Limpieza finalizada. Log: "%LOG_FILE%"
echo.
echo Borra solo (lista blanca):
echo   - __pycache__ y *.pyc/*.pyo
echo   - .ruff_cache
echo   - tools\*.download
echo   - logs\*.log con mas de %DAYS_LOGS% dias
echo   - debug-*.log (raiz) con mas de %DAYS_LOGS% dias
echo   - web_data\uploads archivos con mas de %DAYS_UPLOADS% dias
echo.
exit /b 0

