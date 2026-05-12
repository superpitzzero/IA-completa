@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Nexo - Lanzador Web Todo En Uno
color 0A
cd /d "%~dp0"

echo.
echo  ============================================================
echo   NEXO - LANZADOR WEB TODO EN UNO
echo   Arranca Ollama, web local y URL publica (Cloudflare Tunnel)
echo  ============================================================
echo.

set "PY_EXE="
set "PY_ARGS="

if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
)

if not defined PY_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PY_EXE set "PY_EXE=%%P"
    )
)

if not defined PY_EXE (
    for /f "delims=" %%P in ('where py 2^>nul') do (
        if not defined PY_EXE (
            set "PY_EXE=%%P"
            set "PY_ARGS=-3"
        )
    )
)

if not defined PY_EXE (
    echo  [ERROR] Python no encontrado.
    echo  Instala Python 3.10+ desde https://python.org
    echo.
    pause
    exit /b 1
)

echo  Python detectado:
"%PY_EXE%" %PY_ARGS% --version
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo ejecutar Python.
    echo.
    pause
    exit /b 1
)

echo.
set "NEXO_WEB_PY_EXE=%PY_EXE%"
set "NEXO_WEB_PY_ARGS=%PY_ARGS%"
set "IA_WEB_PY_EXE=%PY_EXE%"
set "IA_WEB_PY_ARGS=%PY_ARGS%"
if not defined NEXO_CLEAN_PREVIOUS_TUNNELS set "NEXO_CLEAN_PREVIOUS_TUNNELS=1"
set "NEXO_OLLAMA_PID_FILE=%~dp0logs\ollama_started_by_launcher.json"
set "IA_OLLAMA_PID_FILE=%NEXO_OLLAMA_PID_FILE%"

rem Perfil de rendimiento para i7-9700K + GTX 1080 Ti.
if not defined IA_MODEL_PROFILE set "IA_MODEL_PROFILE=fast"
if not defined IA_OLLAMA_NUM_THREAD set "IA_OLLAMA_NUM_THREAD=8"
if not defined IA_NUM_CTX_ARQUITECTO set "IA_NUM_CTX_ARQUITECTO=4096"
if not defined IA_NUM_CTX_PROGRAMADOR set "IA_NUM_CTX_PROGRAMADOR=4096"
if not defined IA_NUM_BATCH_ARQUITECTO set "IA_NUM_BATCH_ARQUITECTO=256"
if not defined IA_NUM_BATCH_PROGRAMADOR set "IA_NUM_BATCH_PROGRAMADOR=512"
if not defined IA_OLLAMA_KEEP_ALIVE set "IA_OLLAMA_KEEP_ALIVE=45m"

rem Cloudflare por defecto salvo que otro launcher lo sobreescriba
if not defined NEXO_TUNNEL set "NEXO_TUNNEL=cloudflare"
if not defined IA_TUNNEL set "IA_TUNNEL=cloudflare"

"%PY_EXE%" %PY_ARGS% "%~dp0launch_web.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo  [ERROR] El lanzador termino con errores. Revisa los mensajes anteriores.
) else (
    echo  [OK] Lanzador completado.
)
echo.
pause
exit /b %EXIT_CODE%
