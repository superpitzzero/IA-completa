@echo off
REM ============================================================
REM  NEXO - LANZADOR OPTIMIZADO PARA 9-50 USUARIOS CONCURRENTES
REM  Hardware: i7-9700K + 32 GB RAM + GTX 1080 Ti 11 GB
REM ============================================================
REM
REM  Diferencias clave frente a LANZAR_TODO_WEB.bat / LANZAR_ULTRA_RAPIDO.bat:
REM
REM   1) WSGI con Waitress (NEXO_USE_WAITRESS=1) en lugar del server de
REM      desarrollo de Flask -> 2-3x mejor concurrencia con varios usuarios.
REM
REM   2) OLLAMA_NUM_PARALLEL=2 (en vez de 1). Permite que dos usuarios
REM      generen respuestas a la vez sobre el mismo modelo cargado en VRAM.
REM      Con qwen2.5-coder:7b (~4.5 GB) sobra VRAM en la 1080 Ti 11 GB.
REM
REM   3) Forzamos el perfil "fast" (programador y arquitecto = 7B).
REM      El modo COMBINADO ya NO tiene que cambiar de modelo entre fases
REM      (antes 7B -> 14B con MAX_LOADED_MODELS=1 hacia un swap de
REM      ~15-25 s cada mensaje).
REM
REM   4) Warm-up automatico al arrancar: el primer usuario tras lanzar la
REM      web no espera la carga del modelo (se hace en hilo aparte).
REM
REM  Si quieres VOLVER al modelo de calidad maxima (14B) para un usuario
REM  exclusivo, usa LANZAR_TODO_WEB.bat o LANZAR_ULTRA_RAPIDO.bat.
REM ============================================================

setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo.
echo ====================================================
echo  NEXO - Lanzador optimizado MULTI-USUARIO
echo ====================================================
echo.

REM --- Optimizaciones de Ollama ---------------------------------
set OLLAMA_FLASH_ATTENTION=1
set CUDA_VISIBLE_DEVICES=0
REM Permite 2 peticiones en paralelo sobre el mismo modelo (clave multi-usuario):
set OLLAMA_NUM_PARALLEL=2
REM Mantener 1 modelo cargado evita gasto extra de VRAM:
set OLLAMA_MAX_LOADED_MODELS=1
REM Mantener el modelo caliente 60 min:
set OLLAMA_KEEP_ALIVE=60m
set IA_OLLAMA_KEEP_ALIVE=60m
set NEXO_OLLAMA_KEEP_ALIVE=60m

REM --- Perfil "fast" forzado: ambos roles usan 7B -------------
REM Esto evita el swap VRAM (15-25 s) del pipeline combinado.
set IA_MODEL_PROFILE=fast
set IA_MODEL_ARQUITECTO=qwen2.5-coder:7b
set IA_MODEL_PROGRAMADOR=qwen2.5-coder:7b
set IA_GPU_LAYERS_ARQUITECTO=33
set IA_GPU_LAYERS_PROGRAMADOR=33

REM --- CPU/contexto/batch razonables --------------------------
set IA_OLLAMA_NUM_THREAD=8
set IA_NUM_CTX_ARQUITECTO=4096
set IA_NUM_CTX_PROGRAMADOR=4096
set IA_NUM_BATCH_ARQUITECTO=512
set IA_NUM_BATCH_PROGRAMADOR=512

REM --- Servidor web (Waitress) --------------------------------
set NEXO_USE_WAITRESS=1
set NEXO_WAITRESS_THREADS=16
set NEXO_WAITRESS_CONN_LIMIT=200
set NEXO_WAITRESS_CHANNEL_TIMEOUT=600
set NEXO_WARMUP=1
set NEXO_WARMUP_ROLES=arquitecto,programador

echo [CFG] OLLAMA_FLASH_ATTENTION = %OLLAMA_FLASH_ATTENTION%
echo [CFG] OLLAMA_NUM_PARALLEL    = %OLLAMA_NUM_PARALLEL%
echo [CFG] OLLAMA_MAX_LOADED      = %OLLAMA_MAX_LOADED_MODELS%
echo [CFG] OLLAMA_KEEP_ALIVE      = %OLLAMA_KEEP_ALIVE%
echo [CFG] PERFIL                 = %IA_MODEL_PROFILE% (7B para todo)
echo [CFG] WAITRESS THREADS       = %NEXO_WAITRESS_THREADS%
echo [CFG] WARMUP                 = %NEXO_WARMUP%
echo.

REM --- Reusa el flujo existente (Ollama + web + tunel) -------
echo [INFO] Delegando arranque en launch_web.py con la config optimizada...
python launch_web.py %*
set RC=%ERRORLEVEL%
pause 

echo.
echo ====================================================
echo  launch_web.py termino con codigo %RC%
echo ====================================================
endlocal & exit /b %RC%
