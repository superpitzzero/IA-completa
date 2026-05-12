@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Nexo - Diagnostico Completo
color 0B

cd /d "%~dp0"

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG_FILE=%LOG_DIR%\diagnostico_completo.log"

echo.>"%LOG_FILE%"
echo ==============================================================================>>"%LOG_FILE%"
echo  DIAGNOSTICO COMPLETO - Nexo  (%DATE% %TIME%)>>"%LOG_FILE%"
echo ==============================================================================>>"%LOG_FILE%"

echo.
echo  ================================================================
echo   DIAGNOSTICO COMPLETO - Nexo
echo   (Se guarda tambien en: %LOG_FILE%)
echo   Puedes pasar URL publica: DIAGNOSTICO_COMPLETO.bat https://tu-url.ngrok-free.app
echo  ================================================================
echo.

set "PY="
if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
  set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
)
if not defined PY (
  where python >nul 2>&1
  if %errorlevel%==0 set "PY=python"
)
if not defined PY (
  py -3 --version >nul 2>&1
  if %errorlevel%==0 set "PY=py -3"
)
if not defined PY (
  echo [ERROR] Python no encontrado.
  echo [ERROR] Python no encontrado.>>"%LOG_FILE%"
  echo Instala Python 3.10+ desde https://python.org
  pause
  exit /b 1
)

echo [INFO] Python detectado: %PY%
echo [INFO] Python detectado: %PY%>>"%LOG_FILE%"
%PY% --version>>"%LOG_FILE%" 2>&1

echo.
echo =========================
echo  Ejecutando diagnostico_completo.py
echo =========================
echo.
if not "%~1"=="" (
  echo [INFO] Argumentos de diagnostico: %*
  echo [INFO] Argumentos de diagnostico: %*>>"%LOG_FILE%"
)
%PY% diagnostico_completo.py %*
set "RC=%errorlevel%"

echo.
echo =========================
echo  Resultado
echo =========================
if "%RC%"=="0" (
  echo [OK] Todo OK.
) else (
  echo [ERROR] Se detectaron problemas. Revisa el log:
  echo   %LOG_FILE%
)

echo.
echo =========================
echo  Resultado
echo =========================
echo.
echo Listo. Abre el log para ver detalles:
echo   %LOG_FILE%
echo.
pause
exit /b %RC%
