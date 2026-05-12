@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  Configurar URL fija de ngrok
echo  Ejemplo: https://tu-dominio.ngrok-free.app
echo.
set /p "NGROK_URL=URL fija de ngrok: "
if "%NGROK_URL%"=="" (
  echo [ERROR] No escribiste ninguna URL.
  pause
  exit /b 1
)

if not exist "%~dp0web_data" mkdir "%~dp0web_data" >nul 2>&1
>"%~dp0web_data\ngrok_url.txt" echo %NGROK_URL%

echo.
echo [OK] Guardado en web_data\ngrok_url.txt
echo Ahora lanza:
echo   LANZAR_WEB_NGROK.bat
echo.
pause
exit /b 0
