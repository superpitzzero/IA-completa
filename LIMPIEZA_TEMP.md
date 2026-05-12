# Limpieza segura de temporales

Este proyecto incluye `LIMPIAR_TEMP.bat`, que borra **solo** elementos temporales con **lista blanca**.

## Qué borra

- `__pycache__` (en todo el proyecto) y archivos `*.pyc` / `*.pyo`.
- `.ruff_cache`.
- `tools\*.download` (restos de descargas incompletas como `cloudflared.download`).
- `logs\*.log` con más de **14 días** (retención configurable dentro del `.bat`).
- `debug-*.log` en la raíz con más de **14 días**.
- `web_data\uploads\` archivos con más de **14 días** (solo archivos subidos; NO borra `settings.json`, `chats.json`, `memory.json`, `users.json`).

## Qué NO borra

- Código fuente (`*.py`, `*.bat`, etc.).
- Config útil (`web_data\settings.json`, `web_data\ngrok_url.txt`, etc.).
- Datos de chats/memoria/usuarios (`web_data\*.json`).
- Ejecutables de herramientas (`tools\cloudflared.exe`, `tools\ngrok.exe` si existiera).

## Logs de la limpieza

Cada ejecución guarda un log en `logs\limpiar_temp_YYYYMMDD_HHMMSS.log`.

