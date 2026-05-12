# Plan: Chat Multimodal Con Internet Y OpenAI Primero

## Summary
- Convertir la web en un chat multimodal de alcance amplio: documentos, Office, hojas, presentaciones, imÃ¡genes, audio, video, ZIP/7z y binarios desconocidos con metadatos.
- Usar OpenAI primero mediante Responses API con `web_search` automÃ¡tico; si falta clave o falla, responder con Ollama y bÃºsqueda local `ddgs`.
- Arreglar bugs actuales: dependencias nuevas no instaladas por el lanzador, textos con mojibake, fallos silenciosos de adjuntos por paquetes ausentes, y estados poco claros en la UI.

## Key Changes
- AÃ±adir configuraciÃ³n segura en `web_data/settings.json` y variables de entorno. Precedencia: entorno primero, archivo despuÃ©s. Claves: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TRANSCRIBE_MODEL`, `AI_PROVIDER`, `FALLBACK_TO_OLLAMA`.
- Dependencias nuevas/confirmadas: `openai`, `ddgs`, `beautifulsoup4`, `pypdf`, `pillow`, `opencv-python`, `python-docx`, `openpyxl`, `python-pptx`, `moviepy`, `imageio-ffmpeg`, `py7zr`, `python-dotenv`.
- Actualizar `launch_web.py` para instalar y verificar todas las dependencias reales, no solo Flask/Waitress.
- Mantener `/api/chat/stream`, pero ampliar `multipart/form-data` para aceptar casi cualquier archivo. Los formatos conocidos se leen; los desconocidos se guardan, se hashean y se pasan como metadatos.
- Procesamiento de archivos:
  - Texto/cÃ³digo/PDF/Office/hojas/presentaciones: extracciÃ³n local cuando sea posible y subida a OpenAI como `user_data` cuando haya API key.
  - ImÃ¡genes: anÃ¡lisis directo por OpenAI; fallback a `llama3.2-vision`.
  - Audio: transcripciÃ³n con `gpt-4o-transcribe`; fallback a â€œaudio no transcritoâ€ si no hay API.
  - Video: extracciÃ³n de fotogramas con OpenCV y audio con MoviePy; analizar frames + transcript.
  - ZIP/TAR/7z: extracciÃ³n segura con lÃ­mites; analizar archivos internos soportados.
- Internet:
  - OpenAI usa `web_search` en cada respuesta y devuelve fuentes visibles.
  - Si OpenAI no estÃ¡ disponible o no devuelve fuentes Ãºtiles, usar el buscador local `ddgs` con bloqueo SSRF para IPs privadas/locales.
- UI: quitar el filtro rÃ­gido del selector de archivos, mostrar chips con estado de procesamiento, fuentes, proveedor usado, y aviso claro cuando se haya usado fallback local.

## Interfaces
- `web_data/settings.json` opcional:
  ```json
  {
    "ai_provider": "openai",
    "openai_api_key": "",
    "openai_model": "gpt-5.5",
    "openai_transcribe_model": "gpt-4o-transcribe",
    "fallback_to_ollama": true
  }
  ```
- `attachments` en historial se amplÃ­a con: `id`, `filename`, `mime`, `kind`, `size`, `sha256`, `summary`, `status`, `expires_at`, `expired`, `openai_file_id` solo interno.
- Eventos NDJSON nuevos o ampliados: `status`, `sources`, `provider`, `fallback`, `attachment_status`, `token`, `error`, `done`.
- LÃ­mites por defecto: 8 archivos por mensaje, 128 MB total, TTL de 7 dÃ­as, nunca ejecutar archivos subidos.

## Test Plan
- Ejecutar `python -m py_compile orchestrator.py web_app.py launch_web.py test_import.py`.
- Probar con Flask test client y mocks: login, crear chat, `.txt`, `.pdf`, `.docx`, `.xlsx`, imagen, audio, video, ZIP y binario desconocido.
- Verificar que sin `OPENAI_API_KEY` usa Ollama/ddgs sin romper el chat.
- Verificar que con OpenAI mockeado envÃ­a `web_search`, adjuntos y fuentes.
- Probar bloqueo de URLs privadas/locales en bÃºsqueda fallback.
- Probar limpieza de adjuntos caducados y que no expone rutas internas ni API keys al navegador.

## Assumptions And Sources
- Modelo principal por defecto: `gpt-5.5`; editable por entorno o settings. OpenAI lo recomienda para razonamiento/cÃ³digo complejo en sus modelos actuales: https://developers.openai.com/api/docs/models
- IntegraciÃ³n principal: Responses API con `web_search`: https://developers.openai.com/api/docs/guides/tools-web-search
- Archivos OpenAI: `input_file` y Files API con propÃ³sito `user_data`: https://developers.openai.com/api/docs/guides/file-inputs y https://developers.openai.com/api/reference/resources/files
- Audio: usar `gpt-4o-transcribe`: https://developers.openai.com/api/docs/models/gpt-4o-transcribe

