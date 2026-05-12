# 🚀 GUÍA RÁPIDA - Ollama Orchestrator

## ⚡ Inicio Rápido (5 minutos)

```bash
# 1. Instalar dependencias
pip install requests colorama

# 2. Setup inicial (descarga modelos)
python orchestrator.py setup

# 3. Usar
python orchestrator.py chat
```

## 📝 Comandos Más Usados

### Nexo Web Online
```bash
# Lanza Nexo local + Cloudflare/ngrok automatico
LANZAR_TODO_WEB.bat
```

Nexo se abre en `http://localhost:7860` o en el puerto libre que muestre el lanzador. La pagina permite crear cuentas con usuario y contrasena; cada cuenta tiene sus propios chats y memoria.

Si `cloudflared` no esta instalado, el lanzador lo descarga en `tools\cloudflared.exe` y muestra una URL publica `https://...trycloudflare.com`.

Planes locales:

| Plan | Precio | Incluye |
|------|--------|---------|
| Gratis | 0 euros | Modo rapido y prioridad estandar |
| BETA Tester | 5 euros | Modo combinado y mas prioridad entre usuarios |
| Developer | 15 euros | Modo codigo, prioridad maxima y API Key |

Los usuarios sin plan guardado empiezan en `gratis`. Las cuentas `superpitzzero` y `Aerys` estan configuradas como `developer`.

Rendimiento local recomendado para i7-9700K + GTX 1080 Ti:

```bash
set IA_OLLAMA_NUM_THREAD=8
set IA_NUM_CTX_ARQUITECTO=4096
set IA_NUM_CTX_PROGRAMADOR=4096
set IA_NUM_BATCH_ARQUITECTO=256
set IA_NUM_BATCH_PROGRAMADOR=512
```

Estos valores ya son los predeterminados del proyecto. Puedes bajarlos si notas tirones por VRAM o subirlos con cuidado si tienes margen.

Donaciones:

La barra lateral tiene un enlace `Donate` que abre `/donate`. Para activar el boton externo, configura tu enlace real de donacion:

```json
{
  "donate_url": "https://tu-enlace-de-donacion"
}
```

Tambien puedes usar la variable de entorno `NEXO_DONATE_URL` o `DONATE_URL`.

API para Developer:
```bash
curl -X POST http://localhost:7860/api/v1/chat ^
  -H "Authorization: Bearer TU_API_KEY" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Hola\", \"mode\":\"auto\"}"
```

Dependencias web manuales:
```bash
python -m pip install -r requirements_web.txt
```

### Chat Interactivo
```bash
python orchestrator.py chat
```

**Dentro del chat:**
```
/codigo crear API REST con FastAPI
/imagen screenshot.png "¿qué hace este código?"
/salir
```

### Generar Código (CLI)
```bash
# Básico
python orchestrator.py codigo "crear web scraper con BeautifulSoup"

# Específico
python orchestrator.py codigo "función Python para validar emails con regex"

# Proyecto completo
python orchestrator.py codigo "aplicación Flask con login JWT y CRUD de usuarios"
```

### Analizar Imágenes
```bash
# Descripción general
python orchestrator.py imagen foto.jpg

# Pregunta específica
python orchestrator.py imagen diagrama.png "explica esta arquitectura"

# Analizar código en captura
python orchestrator.py imagen codigo.png "¿qué bugs tiene este código?"
```

## 🎯 Casos de Uso Comunes

### 1. Debugging
```bash
python orchestrator.py chat
> Tengo este error: [pega el error]
> ¿Puedes ayudarme a solucionarlo?
```

### 2. Code Review
```bash
python orchestrator.py codigo "revisa este código: [pega código]"
```

### 3. Aprender Nuevas Tecnologías
```bash
python orchestrator.py codigo "ejemplo básico de React hooks"
python orchestrator.py codigo "cómo usar asyncio en Python"
```

### 4. Generar Tests
```bash
python orchestrator.py codigo "tests unitarios con pytest para [función]"
```

### 5. Refactorizar
```bash
python orchestrator.py codigo "refactoriza este código aplicando SOLID: [código]"
```

### 6. Documentación
```bash
python orchestrator.py codigo "documenta este código con docstrings: [código]"
```

## 🔧 Configuración Rápida

### Ver Modelos Instalados
```bash
ollama list
```

### Descargar Modelo Manualmente
```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:14b
ollama pull llama3.2-vision:11b
```

### Ajustar VRAM
Edita `orchestrator.py`:
```python
GPU_LAYERS = {
    "arquitecto": 24,   # Más capas = más VRAM
    "programador": 20,
    "vision": 24,
}
```

### Cambiar Modelos
```python
MODELS = {
    "arquitecto": "llama3:8b",      # Modelo alternativo
    "programador": "codellama:7b",
    "vision": "llava:7b",
}
```

## 💡 Tips Pro

### 1. Prompts Efectivos
```bash
❌ "haz una web"
✅ "crea aplicación Flask con registro de usuarios, login JWT, y CRUD de tareas"

❌ "código python"  
✅ "función Python que lee CSV, valida emails, y exporta a JSON con logging"
```

### 2. Especifica el Lenguaje
```bash
"API REST en Python con FastAPI"
"componente React con hooks"
"script Bash para backup automatizado"
```

### 3. Pide Tests
```bash
"crea clase Calculator en Python CON tests unitarios"
```

### 4. Arquitectura Primero
```bash
"diseña la arquitectura de un sistema de chat en tiempo real, luego implementa el backend"
```

## 🐛 Troubleshooting Rápido

### Problema: "Connection refused"
```bash
# Solución
ollama serve
```

### Problema: Modelo lento
```python
# Reduce capas GPU en el script
GPU_LAYERS = {
    "arquitecto": 12,  # Reduce de 18 a 12
}
```

### Problema: Out of memory
```bash
# Cierra otras apps
# O usa modelo más pequeño:
MODELS = {
    "arquitecto": "qwen2.5-coder:7b",  # En vez de 14b
}
```

### Problema: Código truncado
```bash
# En el chat, pide explícitamente:
"muestra el código COMPLETO, sin omitir nada"
```

## 📊 Comparación de Modelos

| Modelo | Tamaño | VRAM | Velocidad | Calidad | Uso |
|--------|--------|------|-----------|---------|-----|
| 1.5B | 1.2GB | ⚡⚡⚡ | ⭐⭐ | Autocompletado |
| 7B | 4.5GB | ⚡⚡ | ⭐⭐⭐ | Código general |
| 14B | 10GB | ⚡ | ⭐⭐⭐⭐ | Review/arquitectura |
| Vision 11B | 8GB | ⚡ | ⭐⭐⭐ | Análisis imágenes |

## 🎓 Recursos

### Documentación Ollama
```bash
ollama --help
ollama run --help
```

### Ver Logs
```bash
# Linux/Mac
journalctl -u ollama -f

# Windows
# Busca en visor de eventos
```

### Community
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Ollama Discord](https://discord.gg/ollama)
- [Qwen Models](https://huggingface.co/Qwen)

## 🔥 Scripts One-Liners

### Generar proyecto completo
```bash
python -c "from orchestrator import *; start_ollama(); pipeline_codigo('crear proyecto FastAPI con Docker, tests, y CI/CD')"
```

### Batch code review
```bash
for f in *.py; do python orchestrator.py codigo "revisa $f"; done
```

### Análisis de screenshots
```bash
for img in screenshots/*.png; do python orchestrator.py imagen "$img"; done
```

## ⚙️ Integración con Editores

### VS Code
1. Usa Continue extension
2. Configura Ollama como provider
3. O usa el script directamente desde terminal integrada

### Vim/Neovim
```bash
# En visual mode, selecciona código y:
:'<,'>!python orchestrator.py codigo "mejora este código"
```

### Jupyter
```python
from orchestrator import call_ollama

# En celda
codigo = call_ollama("programador", "función para procesar dataframe", stream=False)
print(codigo)
```

## 📈 Optimización

### Calentar modelo (primera ejecución lenta)
```bash
ollama run qwen2.5-coder:7b "test"
```

### Mantener en memoria
```python
# En el script, cambia:
"keep_alive": 300  # 5 minutos
```

### Procesar en batch
```python
# Usa ejemplos_avanzados.py para procesar múltiples archivos
```

---

**¿Necesitas más ayuda?** Consulta el README.md completo
