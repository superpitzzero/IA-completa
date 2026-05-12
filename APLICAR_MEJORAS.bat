@echo off
chcp 65001 >nul
title Nexo Mejoras — Patcher

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   NEXO MEJORAS — Patcher automático v1.0    ║
echo  ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Verificar que web_app.py existe
if not exist "web_app.py" (
    echo [ERROR] No se encontro web_app.py en esta carpeta.
    echo         Asegurate de ejecutar este .bat desde la carpeta del proyecto.
    pause
    exit /b 1
)

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH.
    pause
    exit /b 1
)

REM Instalar dependencias nuevas
echo [INFO] Instalando dependencias nuevas...
python -m pip install psutil GPUtil --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [AVISO] Algunas dependencias no se pudieron instalar (GPU monitor podria no funcionar)
)

echo.
echo [INFO] Aplicando parches a web_app.py...
echo.

python nexo_patch.py
if errorlevel 1 (
    echo.
    echo [ERROR] El patcher devolvio un error.
    echo         Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Configuracion opcional (edita este .bat o
echo   crea un archivo .env con estos valores):
echo.
echo   NEXO_INVITE_CODES=tu_codigo,otro_codigo
echo   NEXO_RATE_LIMIT_MAX=5
echo   NEXO_RATE_LIMIT_WINDOW=60
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo Ahora ejecuta LANZAR_TODO_WEB.bat para iniciar Nexo.
echo.
pause
