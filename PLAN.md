# Web Online de Nexo Para NEXO

## Resumen
Crear una web propia, no dependiente de Open WebUI, que corra en tu PC junto a Ollama y se publique por internet con Cloudflare Tunnel. La web tendrÃ¡ una interfaz de Nexo, login con un Ãºnico usuario comÃºn, chat con selector de modo de IA y memoria compartida guardada en archivos locales.

## Cambios Clave
- AÃ±adir una app web Flask servida con Waitress:
  - Dependencias nuevas: `flask`, `waitress`.
  - Reutilizar `orchestrator.py` para hablar con Ollama y sus modelos actuales: `qwen2.5-coder:14b`, `qwen2.5-coder:7b`, `llama3.2-vision:11b`.
  - Crear `web_app.py` como servidor web principal.
- Crear UI estilo ChatGPT:
  - Pantalla de login.
  - Sidebar con â€œNuevo chatâ€, historial de chats y selector de modo.
  - Panel principal con mensajes, streaming visual de respuesta, caja de texto fija abajo y diseÃ±o responsive.
  - Render bÃ¡sico de Markdown y bloques de cÃ³digo con botÃ³n copiar.
- AÃ±adir tres modos de IA en el selector:
  - `Rapido`: una llamada directa al modelo arquitecto.
  - `Combinado`: el programador genera borrador y el arquitecto revisa/mejora la respuesta final.
  - `Codigo`: variante enfocada a programaciÃ³n, usando prompts de programador + arquitecto sin preguntas interactivas.
- AÃ±adir autenticaciÃ³n por archivo:
  - Carpeta local `web_data/`.
  - Archivo `web_data/users.json` editable inicialmente con:
    ```json
    {"username": "admin", "password": "TU_CONTRASEÃ‘A"}
    ```
  - En el primer arranque, convertir `password` a `password_hash` y borrar la contraseÃ±a en texto plano.
  - Sesiones con cookie segura, `HttpOnly`, `SameSite=Lax`.
  - Rate limit simple de login para evitar fuerza bruta bÃ¡sica.
- AÃ±adir memoria compartida:
  - `web_data/chats.json` guarda conversaciones.
  - `web_data/memory.json` guarda un resumen global de memoria.
  - Cada respuesta usa el resumen + los Ãºltimos mensajes del chat.
  - DespuÃ©s de responder, actualizar el resumen en segundo plano; si falla, el chat sigue funcionando.
- AÃ±adir lanzador online:
  - Crear `LANZAR_WEB_ONLINE.bat`.
  - Verifica Python, instala dependencias, arranca Ollama si hace falta, inicia la web en `127.0.0.1:7860`.
  - Si `cloudflared` estÃ¡ instalado, abre:
    ```bat
    cloudflared tunnel --url http://127.0.0.1:7860
    ```
  - Mostrar la URL pÃºblica `trycloudflare.com`.
  - Si falta Cloudflare Tunnel, indicar:
    ```bat
    winget install Cloudflare.cloudflared
    ```

## Interfaces
- Rutas web:
  - `GET /login`, `POST /login`, `POST /logout`
  - `GET /` interfaz principal protegida
  - `GET /api/chats`, `POST /api/chats`, `GET /api/chats/<id>`
  - `POST /api/chat/stream` para enviar mensaje y recibir respuesta progresiva
  - `GET /api/memory`, `POST /api/memory/clear`
- Formato de mensaje:
  ```json
  {
    "chat_id": "id",
    "mode": "rapido|combinado|codigo",
    "message": "texto del usuario"
  }
  ```

## Pruebas
- Ejecutar:
  ```bat
  python -m py_compile orchestrator.py web_app.py
  ```
- Probar login:
  - Sin sesiÃ³n, `/` redirige a `/login`.
  - ContraseÃ±a incorrecta no entra.
  - ContraseÃ±a correcta entra.
  - Tras primer arranque, `users.json` no conserva `password` en texto plano.
- Probar chat:
  - Crear chat nuevo.
  - Enviar mensaje en modo `Rapido`.
  - Enviar mensaje en modo `Combinado`.
  - Enviar peticiÃ³n de cÃ³digo en modo `Codigo`.
  - Recargar pÃ¡gina y comprobar que el historial sigue.
  - Comprobar que `memory.json` se actualiza.
- Probar fallos:
  - Ollama apagado muestra error claro en UI.
  - Modelo no disponible muestra aviso claro.
  - Usuario no autenticado no puede llamar a `/api/chat/stream`.
- Probar online:
  - Ejecutar `LANZAR_WEB_ONLINE.bat`.
  - Abrir la URL local.
  - Abrir la URL de Cloudflare desde otro dispositivo.
  - Confirmar que pide login antes de mostrar el chat.

## Supuestos
- â€œCualquiera puede entrarâ€ significa cualquiera con la URL pÃºblica y la contraseÃ±a comÃºn.
- La memoria serÃ¡ compartida porque elegiste un Ãºnico login comÃºn.
- Por seguridad, la contraseÃ±a se configura editando un archivo, pero se guarda finalmente como hash, no en texto plano.
- La app correrÃ¡ en tu PC para usar tu Ollama/GPU local; Cloudflare Tunnel serÃ¡ el mÃ©todo online por defecto.

