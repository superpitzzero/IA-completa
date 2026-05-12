# Archivos + Internet Para NEXO Web

## Resumen
- Ampliar `web_app.py` para que el chat web acepte adjuntos: imÃ¡genes, PDFs, texto/CSV/Markdown/cÃ³digo y videos.
- Activar bÃºsqueda por internet en cada mensaje, usando la conexiÃ³n del PC y una opciÃ³n sin API key basada en `ddgs`.
- Guardar archivos durante 7 dÃ­as en `web_data/uploads/`, manteniendo en el historial el nombre, tipo, resumen/texto extraÃ­do y estado del archivo.
- El video se analizarÃ¡ de forma detallada por fotogramas clave, no por audio ni reproducciÃ³n completa.

## Cambios Clave
- Dependencias nuevas en `requirements_web.txt`: `ddgs`, `beautifulsoup4`, `pypdf`, `pillow`, `opencv-python`.
- Subir `MAX_CONTENT_LENGTH` desde `512 KB` a un lÃ­mite apto para multimedia, con validaciÃ³n propia por tipo:
  - ImÃ¡genes: `jpg/jpeg/png/webp/bmp/gif`.
  - Documentos: `pdf/txt/md/csv/json/py/js/html/css/log`.
  - Video: `mp4/webm/mov/avi/mkv`.
- Cambiar `/api/chat/stream` para aceptar `multipart/form-data` con `chat_id`, `mode`, `message` y `files[]`, manteniendo JSON como fallback para mensajes sin archivos.
- AÃ±adir UI de adjuntos al compositor: botÃ³n de archivo, arrastrar/soltar, pegar imagen, chips con nombre/tamaÃ±o, preview de imagen y botÃ³n quitar antes de enviar.

## Procesamiento IA
- Para documentos, extraer texto localmente: texto plano directo y PDF con `pypdf`, truncando por seguridad antes de meterlo al prompt.
- Para imÃ¡genes y fotogramas de video, usar el modelo `vision` de Ollama para crear un resumen visual; ese resumen se aÃ±ade al contexto que luego usan los modos `rapido`, `combinado` y `codigo`.
- Para video â€œmÃ¡s detalladoâ€, extraer hasta 24 fotogramas distribuidos por duraciÃ³n, redimensionados a mÃ¡ximo `1024px`, y guardarlos como derivados temporales.
- Antes de cada respuesta, ejecutar bÃºsqueda web con `ddgs`, tomar los mejores resultados, descargar hasta 3 pÃ¡ginas pÃºblicas con `requests`, limpiarlas con `beautifulsoup4` y pasar un bloque â€œContexto de internetâ€ al prompt.
- AÃ±adir fuentes al historial y a la UI mediante un evento streaming nuevo `sources`, mostrando tÃ­tulo + URL al final de la respuesta.

## Seguridad Y Datos
- Guardar archivos bajo `web_data/uploads/<user_id>/<chat_id>/` con nombres saneados e IDs Ãºnicos; nunca ejecutar archivos subidos.
- Bloquear lectura web de URLs locales/privadas: `localhost`, `127.0.0.1`, IPs LAN, `file://` y rangos reservados, para evitar que usuarios externos usen la web pÃºblica contra servicios internos.
- Ejecutar limpieza al arrancar y tras subidas: borrar archivos con mÃ¡s de 7 dÃ­as; dejar metadatos en el chat marcados como caducados.
- Esquema nuevo opcional en mensajes:
  - `attachments`: lista con `id`, `filename`, `mime`, `kind`, `size`, `summary`, `expires_at`.
  - `sources`: lista con `title`, `url`, `snippet`.

## Test Plan
- Ejecutar `python -m py_compile orchestrator.py web_app.py`.
- Probar con Flask test client:
  - Usuario no autenticado no puede subir ni chatear.
  - Mensaje multipart con `.txt` crea chat, guarda metadatos y aÃ±ade texto extraÃ­do al contexto.
  - Archivo no permitido o demasiado grande devuelve error claro.
  - BÃºsqueda web mockeada aÃ±ade `sources` y no rompe si una pÃ¡gina falla.
- Pruebas manuales:
  - Subir imagen y preguntar quÃ© aparece.
  - Subir PDF/TXT y pedir resumen.
  - Subir video corto y verificar anÃ¡lisis por fotogramas.
  - Confirmar que cada respuesta intenta buscar en internet y muestra fuentes.
  - Cambiar fecha/archivos antiguos y comprobar limpieza de 7 dÃ­as.

## Supuestos
- La bÃºsqueda serÃ¡ siempre activa, como elegiste, salvo fallo tÃ©cnico; si falla, la IA responde igualmente avisando que no pudo consultar internet.
- No se aÃ±ade transcripciÃ³n de audio en esta versiÃ³n.
- Fuentes verificadas para dependencias: `ddgs` en PyPI https://pypi.org/project/ddgs/, `pypdf` en PyPI https://pypi.org/project/pypdf/, `opencv-python` en PyPI https://pypi.org/project/opencv-python/.

