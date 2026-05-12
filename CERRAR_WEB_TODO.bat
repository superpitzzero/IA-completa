@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

if not exist "logs" mkdir "logs" >nul 2>nul

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
    echo [ERROR] Python no encontrado.
    exit /b 1
)

"%PY_EXE%" %PY_ARGS% "%~dp0tools\cerrar_web.py"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo [ERROR] El cierre termino con errores. Revisa logs\cerrar_web_*.log
) else (
  echo [OK] Cierre finalizado. Revisa logs\cerrar_web_*.log
)
echo.
exit /b %EXIT_CODE%

