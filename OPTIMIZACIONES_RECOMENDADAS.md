# ⚡ OPTIMIZACIONES PARA NEXO (multiusuario 9-50 personas)

> Hardware objetivo: **i7-9700K + 32 GB RAM + GTX 1080 Ti 11 GB**
> Caso de uso: web pública con 9-50 usuarios concurrentes vía TikTok.
> Fecha: 2026-01

---

## 📋 Resumen ejecutivo

El proyecto era **lento con varios usuarios** por 5 motivos concretos. Tras aplicar los fixes de esta guía se esperan estas mejoras:

| Métrica | Antes | Después |
|---|---|---|
| Servidor HTTP | Werkzeug dev (mononúcleo real) | Waitress (multi-hilo real) |
| Concurrencia ~5 usuarios | uno espera al otro | 2 en paralelo, resto en cola corta |
| Modo combinado (latencia) | 20-40 s (swap VRAM 7B↔14B) | 5-12 s (sin swap) |
| Primer mensaje tras arranque | 15-25 s (carga modelo) | <2 s (warm-up previo) |
| Conexiones simultáneas máx | ~10 antes de bloqueo | 200 (limit Waitress) |

---

## ✅ Cambios ya aplicados al proyecto

### 1. `web_app.py` — Servidor Waitress + warm-up
Se sustituyó `app.run(...)` por `waitress.serve(...)` en `main()`. El servidor de desarrollo de Flask (`app.run`) **no es apto para producción** y serializa peticiones aunque pongas `threaded=True`.

Nuevas variables de entorno soportadas:
- `NEXO_USE_WAITRESS=1` (por defecto). Pon `0` para volver a Werkzeug.
- `NEXO_WAITRESS_THREADS=16` — número de hilos del WSGI.
- `NEXO_WAITRESS_CONN_LIMIT=200` — conexiones simultáneas.
- `NEXO_WAITRESS_CHANNEL_TIMEOUT=600` — segundos máximos por conexión (suficiente para respuestas largas de Ollama).
- `NEXO_WARMUP=1` (por defecto). Lanza un mensaje "OK" interno a Ollama al arrancar para que el primer usuario no espere.
- `NEXO_WARMUP_ROLES=arquitecto,programador` — roles que se precargan.

### 2. `LANZAR_MULTIUSUARIO.bat` (NUEVO)
Lanzador específico para multi-usuario. Diferencias clave frente a `LANZAR_TODO_WEB.bat`:

| Variable | LANZAR_TODO_WEB.bat | **LANZAR_MULTIUSUARIO.bat** |
|---|---|---|
| `OLLAMA_NUM_PARALLEL` | 1 | **2** |
| `OLLAMA_MAX_LOADED_MODELS` | 1 | 1 |
| `IA_MODEL_PROFILE` | (turbo: 14B+7B) | **fast: 7B+7B** |
| `IA_MODEL_ARQUITECTO` | qwen2.5-coder:14b | **qwen2.5-coder:7b** |
| `NEXO_USE_WAITRESS` | (no se usaba) | **1** |
| `NEXO_WARMUP` | — | **1** |

**Uso**: doble clic en `LANZAR_MULTIUSUARIO.bat`. Igual que el original, pero optimizado para la web pública.

---

## 🔍 Causa raíz de la lentitud — explicación técnica

### Cuello 1: `app.run()` no es un servidor de producción
`web_app.py` líneas 5749-5753 usaban `app.run(threaded=True)`. Werkzeug spawnea un hilo por conexión pero:
- No tiene control de backpressure (rechaza conexiones bajo carga).
- Usa el GIL de forma agresiva en sockets.
- No es estable con streams largos NDJSON (de hecho lo decía el comentario del propio archivo).

**Waitress** es un WSGI server real (mismo motor que muchos sitios Python en producción), con pool de hilos, gestión de conexiones y backpressure adecuado.

### Cuello 2: `OLLAMA_NUM_PARALLEL=1`
Esta variable de Ollama limita el **número de peticiones procesadas a la vez sobre el mismo modelo**. Con `=1`, si dos usuarios envían mensaje simultáneamente, el segundo espera a que termine el primero (esto **NO depende** de Flask ni de Waitress).

Con tu GPU (11 GB) y modelo 7B (~4.5 GB), poner `=2` cabe sobradamente y duplica el throughput real.

Si quisieras `=3` o `=4`, necesitarías comprobar:
- VRAM libre tras cargar el modelo (`nvidia-smi`).
- Que el aumento de KV-cache no te quede sin VRAM (cada slot paralelo añade ~500-700 MB para ctx 4096).

### Cuello 3: Pipeline combinado con DOS modelos distintos
El código de `web_app.py` (líneas 4655-4686) hace:
1. Borrador con `programador` (qwen2.5-coder:**7b**)
2. Revisión final con `arquitecto` (qwen2.5-coder:**14b**)

Con `OLLAMA_MAX_LOADED_MODELS=1` (necesario por VRAM), Ollama **descarga el 7B y carga el 14B**. Eso son 15-25 segundos perdidos POR CADA MENSAJE en modo combinado.

**Solución elegida**: forzar `IA_MODEL_ARQUITECTO=qwen2.5-coder:7b`. Ambas fases usan el mismo modelo cargado en VRAM → 0 swap.

> **Calidad**: bajas un poco la calidad de la revisión final, pero a cambio la respuesta llega 3-4 veces más rápido. Para usuarios de TikTok (preguntas casuales/código sencillo) la diferencia se nota poco.
>
> Si algún usuario "Developer" quiere calidad 14B, puedes mantener `LANZAR_ULTRA_RAPIDO.bat` en paralelo (no para la web pública).

### Cuello 4: Sin warm-up
El primer mensaje tras arrancar tardaba 15-25 s porque Ollama carga el modelo bajo demanda. El warm-up nuevo lanza una llamada `"OK"` con `num_predict=1` desde un hilo daemon al arrancar el servidor.

### Cuello 5: Cloudflare Tunnel (~150-300 ms extra)
Cloudflare Tunnel es cómodo pero añade latencia. Si tienes DuckDNS configurado (ya tienes scripts), `DUCKDNS_CONFIGURAR.bat` + abrir el puerto en el router te da conexión directa, sin saltos.

---

## 🧪 Cómo verificar las mejoras

### A) Verifica que Waitress está en uso
Lanza `LANZAR_MULTIUSUARIO.bat` y mira los logs (`logs/web_app.log`). Debe aparecer:
```
[INFO] Waitress: threads=16 connection_limit=200 channel_timeout=600s
```
Si en su lugar ves `Running on http://...`, el servidor de Werkzeug se está usando (revisa `NEXO_USE_WAITRESS`).

### B) Verifica el warm-up
En el log debe aparecer pocos segundos tras arrancar:
```
[WARMUP] arquitecto (qwen2.5-coder:7b) listo en 8.3s
[WARMUP] programador (qwen2.5-coder:7b) listo en 0.1s   <- ya cargado
```

### C) Mide la latencia real
Desde otro terminal, con un usuario logado:
```bash
time curl -X POST http://localhost:7860/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Cookie: <tu_cookie>" \
  -d "{\"chat_id\":\"test\",\"mode\":\"combinado\",\"message\":\"hola\"}" \
  -o respuesta.txt
```
Compara con `LANZAR_TODO_WEB.bat`: la diferencia en modo combinado debe ser de 15-25 s en el primer mensaje y de ~10 s en los siguientes.

### D) Carga real con varios usuarios simultáneos
Si quieres simular 5 usuarios concurrentes en local:
```powershell
1..5 | ForEach-Object -Parallel {
  curl.exe -X POST http://localhost:7860/api/chat/stream `
    -H "Content-Type: application/json" `
    -d '{"chat_id":"t","mode":"rapido","message":"hola"}'
} -ThrottleLimit 5
```
Con la config nueva las 5 deben completar en ~el tiempo de 2 secuenciales, no de 5.

---

## ⚙️ Tuning fino (opcional)

### Si tienes RAM/VRAM de sobra y quieres MÁS paralelismo
```bat
set OLLAMA_NUM_PARALLEL=3
set NEXO_WAITRESS_THREADS=24
```
Vigila `nvidia-smi` la VRAM y `Administrador de tareas` la RAM bajo carga real.

### Si los logs muestran "context deadline exceeded"
Sube el timeout:
```bat
set NEXO_WAITRESS_CHANNEL_TIMEOUT=900
```
Y en `orchestrator.py` (línea 551) ya hay `timeout=(10, 300)` que es razonable.

### Si quieres priorizar usuarios "developer"/"beta tester"
Esto requiere un cambio de código adicional (cola con prioridad). Si quieres lo añadimos en una iteración futura: usar `queue.PriorityQueue` por plan, con un único worker por modelo. **No incluido en esta entrega.**

### Si quieres mantener el modo combinado con 14B SOLO para developers
Posible vía código: leer plan del usuario y dinámicamente elegir `arquitecto` 7B (gratis/beta) o 14B (developer). **No incluido en esta entrega**, pero es un cambio acotado que se puede pedir.

---

## 📦 Ficheros entregados / modificados

- `web_app.py` — **MODIFICADO**: `main()` ahora usa Waitress + warm-up. Backup automático no se generó (usa Git o copia manual si quieres revertir).
- `LANZAR_MULTIUSUARIO.bat` — **NUEVO**: lanzador optimizado.
- `OPTIMIZACIONES_RECOMENDADAS.md` — **NUEVO**: este documento.

> No se ha tocado `orchestrator.py`. Todas las optimizaciones de Ollama se pasan por variables de entorno desde el `.bat` nuevo (ya soportadas por el orchestrator existente).

---

## ↩️ Cómo revertir si algo va mal

1. **Volver al server Werkzeug**: en una consola antes de lanzar:
   ```bat
   set NEXO_USE_WAITRESS=0
   ```
2. **Desactivar warm-up**:
   ```bat
   set NEXO_WARMUP=0
   ```
3. **Volver a 14B**: usar `LANZAR_TODO_WEB.bat` o `LANZAR_ULTRA_RAPIDO.bat` (no han sido modificados).

---

## 📊 Recomendaciones extra (no obligatorias, sin código)

1. **Cuotas por usuario gratis**: limita 10 mensajes/hora para `gratis` y 50/h para `beta`. Evita que un usuario abuse y sature la cola.
2. **Modo "rapido" por defecto**: el modo combinado consume el doble. Pon `auto` o `rapido` como default en `selectedMode`.
3. **Comprime respuestas**: añadir `gzip` en Waitress no acelera tokens pero sí HTML/JSON estático.
4. **Métricas reales**: añade un endpoint `/admin/stats` que registre tokens/s y tiempo medio por modo. Permite afinar.

---

✏️ **Cualquier duda o si quieres que añada cola con prioridad por plan / 14B solo para developers / rate-limit por IP, dímelo y lo implemento en la siguiente iteración.**
