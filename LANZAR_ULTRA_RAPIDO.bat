@echo off
chcp 65001 >nul
title Nexo IA — ULTRA RÁPIDO (GTX 1080 Ti)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   NEXO — LANZADOR ULTRA RÁPIDO                              ║
echo ║   GTX 1080 Ti 11GB · i7-9700K 8C · 32 GB DDR4 3000         ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ══════════════════════════════════════════════════════
::  OPTIMIZACIONES DE OLLAMA PARA GTX 1080 Ti (Pascal)
:: ══════════════════════════════════════════════════════

:: Flash Attention v2 — acelera la fase de atención 2-4x en Pascal+
set OLLAMA_FLASH_ATTENTION=1

:: Usa solo la GTX 1080 Ti (GPU 0)
set CUDA_VISIBLE_DEVICES=0

:: 1 solicitud a la vez = máximo rendimiento por solicitud
:: (para multiusuario, cambia a 2 o 3 según carga)
set OLLAMA_NUM_PARALLEL=1

:: Solo 1 modelo en VRAM a la vez = más VRAM disponible por modelo
set OLLAMA_MAX_LOADED_MODELS=1

:: Mantenemos el modelo caliente 10 minutos tras el último uso
set OLLAMA_KEEP_ALIVE=10m

:: Hilos CPU exactos del i7-9700K (8 núcleos físicos, sin HT)
set IA_OLLAMA_NUM_THREAD=8

:: GPU layers optimizados para 11 GB VRAM
set IA_GPU_LAYERS_ARQUITECTO=35
set IA_GPU_LAYERS_PROGRAMADOR=33
set IA_GPU_LAYERS_VISION=30
set IA_GPU_LAYERS_RAPIDO=33

:: Perfil turbo (calidad máxima con velocidad)
set IA_MODEL_PROFILE=turbo

:: ══════════════════════════════════════════════════════
::  ARRANCAR
:: ══════════════════════════════════════════════════════
echo [GPU] OLLAMA_FLASH_ATTENTION = %OLLAMA_FLASH_ATTENTION%
echo [GPU] CUDA_VISIBLE_DEVICES   = %CUDA_VISIBLE_DEVICES%
echo [GPU] LAYERS arquitecto=%IA_GPU_LAYERS_ARQUITECTO%  programador=%IA_GPU_LAYERS_PROGRAMADOR%  vision=%IA_GPU_LAYERS_VISION%
echo [CPU] Threads = %IA_OLLAMA_NUM_THREAD%  (i7-9700K 8C)
echo.
echo Iniciando Ollama con Flash Attention...
start "" "ollama" serve
timeout /t 3 /nobreak >nul

echo Iniciando servidor web Nexo...
python launch_web.py

pause
