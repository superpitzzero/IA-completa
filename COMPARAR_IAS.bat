@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ============================================================
REM  COMPARAR_IAS.bat - Menu para lanzar comparar_ias.py
REM  - Sin claves: corre solo IA local
REM  - Con claves: puedes elegir providers remotos
REM ============================================================

set "ROOT=%~dp0"
set "PY=python"
set "SCRIPT=%ROOT%comparar_ias.py"
set "DEFAULT_INPUT=%ROOT%prompts\bench.json"
set "OUT_DIR=%ROOT%logs\comparativas"

if not exist "%SCRIPT%" (
  echo [ERROR] No existe: "%SCRIPT%"
  pause
  exit /b 1
)

if not exist "%OUT_DIR%" (
  mkdir "%OUT_DIR%" >nul 2>&1
)

:menu
cls
echo ============================================================
echo   COMPARADOR DE IAs (local vs ChatGPT/Claude/Gemini)
echo ============================================================
echo.
echo Detectando claves en variables de entorno:
if defined OPENAI_API_KEY (echo  - OPENAI_API_KEY: SI) else (echo  - OPENAI_API_KEY: NO)
if defined ANTHROPIC_API_KEY (echo  - ANTHROPIC_API_KEY: SI) else (echo  - ANTHROPIC_API_KEY: NO)
if defined GEMINI_API_KEY (echo  - GEMINI_API_KEY: SI) else if defined GOOGLE_API_KEY (echo  - GOOGLE_API_KEY: SI (GOOGLE_API_KEY)) else (echo  - GEMINI/GOOGLE API KEY: NO)
echo.
echo Elige set de prompts:
echo  1) bench.json (default)
echo  2) Especificar ruta .json/.csv/.tsv
echo.
set /p "PSET=Opcion [1-2] (Enter=1): "
if "%PSET%"=="" set "PSET=1"
if "%PSET%"=="1" (
  set "INPUT=%DEFAULT_INPUT%"
) else if "%PSET%"=="2" (
  set /p "INPUT=Ruta input: "
) else (
  echo Opcion invalida.
  pause
  goto menu
)

echo.
echo Elige providers:
echo  1) auto (local + remotos con clave)
echo  2) local
echo  3) all (intenta todos, aunque falten claves)
echo  4) lista (ej: local,openai,anthropic,gemini)
echo.
set /p "P=Opcion [1-4] (Enter=1): "
if "%P%"=="" set "P=1"
if "%P%"=="1" (
  set "PROVIDER=auto"
) else if "%P%"=="2" (
  set "PROVIDER=local"
) else if "%P%"=="3" (
  set "PROVIDER=all"
) else if "%P%"=="4" (
  set /p "PROVIDER=Providers (comma): "
) else (
  echo Opcion invalida.
  pause
  goto menu
)

echo.
echo Modelo local:
echo  - Para Nexo/Ollama integrado: programador ^| arquitecto ^| vision
echo  - O un modelo Ollama por nombre, ej: qwen2.5-coder:7b
set /p "MODEL=Model local (Enter=programador): "
if "%MODEL%"=="" set "MODEL=programador"

echo.
echo Opciones:
echo  1) Solo Markdown
echo  2) Markdown + HTML
set /p "FMT=Opcion [1-2] (Enter=2): "
if "%FMT%"=="" set "FMT=2"
set "HTMLFLAG="
if "%FMT%"=="2" set "HTMLFLAG=--html"

echo.
echo Filtro por categoria (opcional): chat ^| code ^| reasoning ^| tool
set /p "CAT=Categoria (Enter=sin filtro): "
set "CATFLAG="
if not "%CAT%"=="" set "CATFLAG=--only-category %CAT%"

echo.
echo Ejecutando...
echo "%PY%" "%SCRIPT%" --provider "%PROVIDER%" --model "%MODEL%" --input "%INPUT%" %HTMLFLAG% %CATFLAG%
echo.

pushd "%ROOT%"
%PY% "%SCRIPT%" --provider "%PROVIDER%" --model "%MODEL%" --input "%INPUT%" %HTMLFLAG% %CATFLAG%
set "EC=%ERRORLEVEL%"
popd

echo.
if "%EC%"=="0" (
  echo Listo. Revisa: "%OUT_DIR%"
) else (
  echo [ERROR] El script devolvio codigo %EC%.
)
echo.
pause
goto menu

