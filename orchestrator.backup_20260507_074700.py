"""
╔══════════════════════════════════════════════════════════════════════╗
║       OLLAMA ORCHESTRATOR SIMPLIFICADO — MULTI-AGENTE               ║
║   Versión optimizada y funcional para GTX 1080 Ti                   ║
╚══════════════════════════════════════════════════════════════════════╝

Requiere: pip install requests colorama
"""

import os
import re
import sys
import json
import time
import base64
import subprocess
import requests
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime


def configure_console_encoding() -> None:
    """Evita fallos al imprimir simbolos Unicode en consolas Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(errors="replace")
            except Exception:
                pass


configure_console_encoding()

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    print("⚠️  Instala colorama: pip install colorama")
    # Fallback sin colores
    class Fore:
        GREEN = YELLOW = RED = CYAN = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════

OLLAMA_HOST = "http://localhost:11434"

# Modelos configurados
MODELS = {
    "arquitecto": "qwen2.5-coder:14b",
    "programador": "qwen2.5-coder:7b",
    "vision": "llama3.2-vision:11b",
}

# Capas GPU para offload RAM (ajusta según tu VRAM disponible)
GPU_LAYERS = {
    "arquitecto": 18,   # ~3.8 GB VRAM
    "programador": 16,  # ~2.3 GB VRAM
    "vision": 20,       # ~4 GB VRAM
}

# Directorio de salida
OUTPUT_DIR = Path("./archivos_generados")
OUTPUT_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════

PROMPT_ARQUITECTO = """Eres un arquitecto de software experto. 
Analiza código, detecta errores, optimiza y proporciona soluciones completas.
Responde con código funcional y completo. Explica tus decisiones técnicas."""

PROMPT_PROGRAMADOR = """Eres un programador experto.
Escribe código limpio, completo y funcional.
Incluye comentarios útiles y manejo de errores.
Piensa antes de codificar."""

PROMPT_VISION = """Eres un analista visual experto.
Analiza imágenes, código en capturas, diagramas y UI.
Proporciona análisis técnico detallado."""

# ═══════════════════════════════════════════════════════════════════════
#  UTILIDADES DE CONSOLA
# ═══════════════════════════════════════════════════════════════════════

def print_banner():
    """Muestra el banner de inicio"""
    print(Fore.CYAN + Style.BRIGHT + """
╔══════════════════════════════════════════════════════════════════════╗
║         OLLAMA ORCHESTRATOR — PIPELINE MULTI-AGENTE                 ║
║  🧠 Arquitecto 14B | 🔨 Programador 7B | 👁️  Visión 11B              ║
╚══════════════════════════════════════════════════════════════════════╝
""")

def ok(msg): print(f"{Fore.GREEN}✅ {msg}")
def warn(msg): print(f"{Fore.YELLOW}⚠️  {msg}")
def error(msg): print(f"{Fore.RED}❌ {msg}")
def info(msg): print(f"{Fore.CYAN}ℹ️  {msg}")

def separator(char="─", width=70):
    print(Fore.CYAN + char * width)

def ask(prompt: str, default: str = "") -> str:
    """Lee entrada del usuario sin lanzar EOFError en entornos no interactivos."""
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print()
        return default

# ═══════════════════════════════════════════════════════════════════════
#  GESTIÓN DE OLLAMA
# ═══════════════════════════════════════════════════════════════════════

def is_ollama_running() -> bool:
    """Verifica si Ollama está corriendo"""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return r.status_code == 200
    except:
        return False

def start_ollama() -> bool:
    """Inicia Ollama si no está corriendo"""
    if is_ollama_running():
        ok("Ollama ya está corriendo")
        return True
    
    info("Iniciando Ollama...")
    ollama_cmd = "ollama"
    
    try:
        # Inicia Ollama en background
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        subprocess.Popen([ollama_cmd, "serve"], **kwargs)
        
        # Espera hasta 15 segundos
        for i in range(15):
            time.sleep(1)
            if is_ollama_running():
                ok("Ollama iniciado correctamente")
                return True
            print(f"  Esperando... {i+1}s", end="\r")
        
        error("Ollama no respondió en 15 segundos")
        return False
    except FileNotFoundError:
        error("Ollama no encontrado. Instálalo desde https://ollama.com")
        return False
    except Exception as e:
        error(f"Error al iniciar Ollama: {e}")
        return False

def get_installed_models() -> List[str]:
    """Obtiene lista de modelos instalados"""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []

def is_model_installed(model_name: str) -> bool:
    """Verifica si un modelo está instalado"""
    target = model_name.lower()
    installed = [m.lower() for m in get_installed_models()]

    if ":" in target:
        return target in installed

    return any(m.split(":", 1)[0] == target for m in installed)

def pull_model(model_name: str) -> bool:
    """Descarga un modelo"""
    info(f"Descargando {model_name}...")
    try:
        result = subprocess.run(["ollama", "pull", model_name])
        if result.returncode == 0:
            ok(f"{model_name} descargado")
            return True
        error(f"Error al descargar {model_name}")
        return False
    except Exception as e:
        error(f"Error: {e}")
        return False

def ensure_models():
    """Verifica que todos los modelos necesarios estén instalados"""
    info("Verificando modelos...")
    
    missing = []
    for role, model in MODELS.items():
        if is_model_installed(model):
            ok(f"{role}: {model}")
        else:
            error(f"{role}: {model} NO INSTALADO")
            missing.append((role, model))
    
    if missing:
        if ask("\n¿Descargar modelos faltantes? (s/n): ", default="n").lower() == 's':
            for role, model in missing:
                pull_model(model)

# ═══════════════════════════════════════════════════════════════════════
#  LLAMADAS A LA API
# ═══════════════════════════════════════════════════════════════════════

def call_ollama(
    model_key: str,
    prompt: str,
    system: str = "",
    images: Optional[List[str]] = None,
    stream: bool = True
) -> str:
    """
    Llama a Ollama con un modelo específico
    
    Args:
        model_key: Clave del modelo en MODELS
        prompt: Prompt del usuario
        system: System prompt
        images: Lista de imágenes en base64 (opcional)
        stream: Si mostrar streaming
    
    Returns:
        Respuesta del modelo
    """
    model = MODELS.get(model_key)
    if not model:
        error(f"Modelo '{model_key}' no definido")
        return ""
    
    # Construir mensaje
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    
    user_msg = {"role": "user", "content": prompt}
    if images:
        user_msg["images"] = images
    messages.append(user_msg)
    
    # Configurar request
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "num_gpu": GPU_LAYERS.get(model_key, 16),
            "temperature": 0.2,
            "top_p": 0.9,
        }
    }
    
    if stream:
        print(f"{Fore.GREEN}[{model_key.upper()}]: ", end="", flush=True)
    
    response_text = ""
    try:
        with requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            stream=stream,
            timeout=300
        ) as resp:
            resp.raise_for_status()
            
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        if stream:
                            print(token, end="", flush=True)
                        response_text += token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
        
        if stream:
            print()  # Nueva línea
        return response_text
    
    except requests.exceptions.Timeout:
        error("\nTimeout - el modelo tardó demasiado")
        return response_text
    except Exception as e:
        error(f"\nError en llamada a Ollama: {e}")
        return response_text

# ═══════════════════════════════════════════════════════════════════════
#  DETECCIÓN Y PROCESAMIENTO DE CÓDIGO
# ═══════════════════════════════════════════════════════════════════════

def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extrae bloques de código de un texto"""
    pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
    blocks = []
    
    for match in pattern.finditer(text):
        lang = match.group(1).lower() or "text"
        code = match.group(2)
        
        # Determinar extensión
        ext_map = {
            "python": ".py", "py": ".py",
            "javascript": ".js", "js": ".js",
            "typescript": ".ts", "ts": ".ts",
            "html": ".html", "css": ".css",
            "bash": ".sh", "shell": ".sh",
            "json": ".json", "yaml": ".yaml",
            "sql": ".sql", "rust": ".rs",
            "go": ".go", "java": ".java",
            "cpp": ".cpp", "c": ".c",
        }
        ext = ext_map.get(lang, ".txt")
        
        if len(code.strip()) > 10:
            blocks.append({
                "lang": lang,
                "code": code,
                "extension": ext
            })
    
    return blocks

def save_code_blocks(blocks: List[Dict], base_name: str = "output") -> List[Path]:
    """Guarda bloques de código en archivos"""
    if not blocks:
        return []
    
    saved = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n{Fore.CYAN}📁 {len(blocks)} bloque(s) de código detectado(s)")
    
    for i, block in enumerate(blocks, 1):
        preview = block["code"][:60].replace("\n", " ")
        print(f"  {i}. [{block['lang'].upper()}] {preview}...")
    
    choice = ask("\n¿Guardar? (s=todos / n=no / 1,2=específicos): ", default="n").lower()
    
    if choice == 'n':
        return []
    
    # Determinar qué guardar
    if choice == 's':
        to_save = list(range(len(blocks)))
    else:
        to_save = []
        for num in choice.split(','):
            if num.strip().isdigit():
                idx = int(num.strip()) - 1
                if 0 <= idx < len(blocks):
                    to_save.append(idx)
    
    # Guardar archivos
    for idx in to_save:
        block = blocks[idx]
        default_name = f"{base_name}_{timestamp}{block['extension']}"
        
        name = ask(f"Nombre para archivo {idx+1} (Enter = {default_name}): ").strip()
        if not name:
            name = default_name
        elif not Path(name).suffix:
            name += block['extension']
        
        filepath = OUTPUT_DIR / name
        filepath.write_text(block["code"], encoding="utf-8")
        ok(f"Guardado: {filepath}")
        saved.append(filepath)
    
    return saved

# ═══════════════════════════════════════════════════════════════════════
#  PROCESAMIENTO DE IMÁGENES
# ═══════════════════════════════════════════════════════════════════════

def load_image_base64(path: str) -> Optional[Tuple[str, str]]:
    """
    Carga una imagen y la convierte a base64
    
    Returns:
        Tupla (base64_data, mime_type) o (None, None) si falla
    """
    # URL
    if path.startswith("http://") or path.startswith("https://"):
        try:
            resp = requests.get(path, timeout=15)
            resp.raise_for_status()
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            data = base64.b64encode(resp.content).decode()
            return data, mime
        except Exception as e:
            error(f"Error descargando imagen: {e}")
            return None, None
    
    # Archivo local
    p = Path(path)
    if not p.exists():
        error(f"Archivo no encontrado: {path}")
        return None, None
    
    supported = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    if p.suffix.lower() not in supported:
        error(f"Formato no soportado: {p.suffix}")
        return None, None
    
    try:
        data = base64.b64encode(p.read_bytes()).decode()
        return data, f"image/{p.suffix[1:]}"
    except Exception as e:
        error(f"Error leyendo imagen: {e}")
        return None, None

# ═══════════════════════════════════════════════════════════════════════
#  PIPELINES
# ═══════════════════════════════════════════════════════════════════════

def pipeline_codigo(prompt: str) -> str:
    """
    Pipeline para generación de código:
    1. Programador genera código inicial
    2. Arquitecto revisa y mejora
    """
    separator()
    print(f"{Fore.MAGENTA}🔨 PIPELINE DE CÓDIGO")
    separator()
    
    # Fase 1: Generación inicial
    info("Fase 1/2: Generando código...")
    codigo_inicial = call_ollama(
        "programador",
        prompt,
        system=PROMPT_PROGRAMADOR
    )
    
    if not codigo_inicial.strip():
        error("No se generó código")
        return ""
    
    # Fase 2: Revisión y mejora
    info("\nFase 2/2: Revisión por arquitecto...")
    prompt_revision = f"""Solicitud original: {prompt}

Código generado:
```
{codigo_inicial}
```

Revisa, corrige y mejora este código. Proporciona la versión final optimizada."""
    
    codigo_final = call_ollama(
        "arquitecto",
        prompt_revision,
        system=PROMPT_ARQUITECTO
    )
    
    separator()
    ok("Pipeline completado")
    
    # Detectar y ofrecer guardar código
    blocks = extract_code_blocks(codigo_final)
    if blocks:
        save_code_blocks(blocks, base_name="codigo")
    
    return codigo_final

def pipeline_vision(prompt: str, image_path: str) -> str:
    """
    Pipeline para análisis de imágenes
    """
    separator()
    print(f"{Fore.MAGENTA}👁️  PIPELINE DE VISIÓN")
    separator()
    
    # Cargar imagen
    info(f"Cargando imagen: {image_path}")
    img_data, mime = load_image_base64(image_path)
    
    if not img_data:
        return ""
    
    # Verificar modelo de visión
    if not is_model_installed(MODELS["vision"]):
        warn("Modelo de visión no instalado")
        if ask("¿Descargar ahora? (s/n): ", default="n").lower() == 's':
            if not pull_model(MODELS["vision"]):
                return ""
        else:
            return ""
    
    # Análisis
    info("Analizando imagen...")
    resultado = call_ollama(
        "vision",
        prompt,
        system=PROMPT_VISION,
        images=[img_data]
    )
    
    separator()
    ok("Análisis completado")
    
    return resultado

def pipeline_simple(prompt: str) -> str:
    """Pipeline simple - solo arquitecto"""
    return call_ollama("arquitecto", prompt, system=PROMPT_ARQUITECTO)

# ═══════════════════════════════════════════════════════════════════════
#  CHAT INTERACTIVO
# ═══════════════════════════════════════════════════════════════════════

def chat_interactivo():
    """Modo chat interactivo"""
    print(f"\n{Fore.CYAN}💬 CHAT INTERACTIVO")
    print("Comandos: /codigo, /imagen <ruta>, /salir")
    separator()
    
    while True:
        try:
            user_input = input(f"\n{Fore.WHITE}Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ['/salir', 'salir', 'exit', 'quit']:
            break
        
        # Comando de código
        if user_input.startswith('/codigo'):
            prompt = user_input[7:].strip()
            if prompt:
                pipeline_codigo(prompt)
            else:
                warn("Uso: /codigo <descripción>")
            continue
        
        # Comando de imagen
        if user_input.startswith('/imagen'):
            parts = user_input[7:].strip().split(maxsplit=1)
            if len(parts) >= 1:
                image_path = parts[0]
                question = parts[1] if len(parts) > 1 else "Analiza esta imagen"
                pipeline_vision(question, image_path)
            else:
                warn("Uso: /imagen <ruta> [pregunta]")
            continue
        
        # Detección automática de intención
        lower = user_input.lower()
        
        # Detectar si pide código
        code_keywords = ["código", "codigo", "programa", "función", "script", 
                        "implementa", "escribe", "crea un", "genera"]
        if any(kw in lower for kw in code_keywords):
            pipeline_codigo(user_input)
        else:
            # Chat simple
            pipeline_simple(user_input)

# ═══════════════════════════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

def menu():
    """Menú principal"""
    print_banner()
    
    if not is_ollama_running():
        if not start_ollama():
            return
    
    ensure_models()
    
    opciones = {
        "1": ("💬 Chat interactivo", chat_interactivo),
        "2": ("🔨 Generar código", lambda: pipeline_codigo(
            ask("Describe el código a generar: ")
        )),
        "3": ("👁️  Analizar imagen", lambda: pipeline_vision(
            ask("¿Qué analizar?: "),
            ask("Ruta de imagen: ")
        )),
        "4": ("📊 Ver modelos instalados", lambda: print("\n".join(
            f"  • {m}" for m in get_installed_models()
        ))),
        "5": ("📥 Descargar modelos", ensure_models),
        "0": ("❌ Salir", None),
    }
    
    while True:
        separator()
        print(f"{Fore.CYAN}MENÚ PRINCIPAL")
        separator()
        
        for key, (label, _) in opciones.items():
            print(f"  {key}. {label}")
        
        choice = ask(f"\n{Fore.WHITE}Opción: ", default="0").strip()
        
        if choice == "0":
            print("\n👋 ¡Hasta pronto!\n")
            break
        
        if choice in opciones and opciones[choice][1]:
            print()
            try:
                opciones[choice][1]()
            except Exception as e:
                error(f"Error: {e}")
        else:
            warn("Opción no válida")

# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Punto de entrada principal"""
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "setup":
            print_banner()
            start_ollama()
            ensure_models()
        
        elif cmd == "chat":
            if not is_ollama_running():
                start_ollama()
            chat_interactivo()
        
        elif cmd == "codigo":
            if len(sys.argv) < 3:
                error("Uso: python orchestrator.py codigo 'descripción'")
                return
            if not is_ollama_running():
                start_ollama()
            pipeline_codigo(" ".join(sys.argv[2:]))
        
        elif cmd == "imagen":
            if len(sys.argv) < 3:
                error("Uso: python orchestrator.py imagen <ruta> ['pregunta']")
                return
            if not is_ollama_running():
                start_ollama()
            img = sys.argv[2]
            pregunta = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "Analiza esta imagen"
            pipeline_vision(pregunta, img)
        
        else:
            print(f"""
Uso: python orchestrator.py [comando]

Comandos:
  setup           - Instalar y configurar modelos
  chat            - Modo chat interactivo
  codigo "desc"   - Generar código
  imagen <ruta>   - Analizar imagen
  
Sin argumentos: Menú interactivo
""")
    else:
        menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.CYAN}👋 Saliendo...\n")
