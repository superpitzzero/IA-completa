"""
╔══════════════════════════════════════════════════════════════════════╗
║    OLLAMA ORCHESTRATOR ─ ULTRA OPTIMIZADO para tu hardware           ║
║    GTX 1080 Ti 11GB · i7-9700K 8C/8T · 32 GB DDR4 3000             ║
╚══════════════════════════════════════════════════════════════════════╝

OPTIMIZACIONES APLICADAS:
  ✔ GPU_LAYERS máximas para 11 GB VRAM (Pascal GP102)
  ✔ Flash Attention habilitado (OLLAMA_FLASH_ATTENTION=1)
  ✔ CPU_THREADS = 8 exacto (i7-9700K sin HyperThreading)
  ✔ NUM_BATCH elevado a 512/1024 para throughput máximo
  ✔ NUM_CTX optimizado: 8192 código / 4096 chat
  ✔ keep_alive = 10m  → modelo caliente, sin esperas de carga
  ✔ Pool HTTP con 32 conexiones (reduce latencia TCP)

VARIABLES DE ENTORNO RECOMENDADAS (ponlas antes de arrancar Ollama):
  set OLLAMA_FLASH_ATTENTION=1
  set CUDA_VISIBLE_DEVICES=0
  set OLLAMA_NUM_PARALLEL=1
  set OLLAMA_MAX_LOADED_MODELS=1
  (o usa el archivo LANZAR_ULTRA_RAPIDO.bat que viene con el parche)

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
import unicodedata
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime


def configure_console_encoding() -> None:
    """Evita fallos al imprimir símbolos Unicode en consolas Windows."""
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
    class Fore:
        GREEN = YELLOW = RED = CYAN = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE MODELOS
# ═══════════════════════════════════════════════════════════════════════

OLLAMA_HOST = "http://localhost:11434"

MODELS = {
    "arquitecto": "qwen2.5-coder:14b",   # Máxima calidad de código
    "programador": "qwen2.5-coder:7b",   # Equilibrio velocidad/calidad
    "vision":      "llama3.2-vision:11b", # Análisis de imágenes
}

# ═══════════════════════════════════════════════════════════════════════
#  GPU: CAPAS OFFLOAD ─ GTX 1080 Ti (11 GB VRAM GDDR5X, Pascal GP102)
# ═══════════════════════════════════════════════════════════════════════
#
# qwen2.5-coder:14b  Q4_K_M ≈ 8.7 GB → 35/40 capas en GPU (queda margen)
# qwen2.5-coder:7b   Q4_K_M ≈ 4.4 GB → 33/32+embed = TODO en GPU
# llama3.2-vision:11b Q4_K_M ≈ 7.0 GB → 30/32 capas en GPU
# qwen2.5:1.5b (router) ≈ 1.0 GB → todo en GPU
#
GPU_LAYERS = {
    "arquitecto": int(os.getenv("IA_GPU_LAYERS_ARQUITECTO", "35")),
    "programador": int(os.getenv("IA_GPU_LAYERS_PROGRAMADOR", "33")),
    "vision":      int(os.getenv("IA_GPU_LAYERS_VISION",      "30")),
    "rapido":      int(os.getenv("IA_GPU_LAYERS_RAPIDO",       "33")),
}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(str(os.getenv(name, "")).strip() or default))
    except ValueError:
        return max(minimum, int(default))


# ═══════════════════════════════════════════════════════════════════════
#  CPU: i7-9700K → 8 núcleos FÍSICOS, SIN HyperThreading
#  Usar exactamente 8 hilos maximiza rendimiento (sin context-switching)
# ═══════════════════════════════════════════════════════════════════════
CPU_THREADS = _env_int("IA_OLLAMA_NUM_THREAD", 8)

# Mantiene el modelo caliente 10 min → 0 latencia de carga
OLLAMA_KEEP_ALIVE = (
    os.getenv("NEXO_OLLAMA_KEEP_ALIVE")
    or os.getenv("IA_OLLAMA_KEEP_ALIVE", "10m")
)

# ═══════════════════════════════════════════════════════════════════════
#  CONTEXTO Y BATCH
#  NUM_CTX  = ventana de contexto (más = más RAM/VRAM)
#  NUM_BATCH = tokens procesados por lote GPU (más = más rápido, más VRAM)
# ═══════════════════════════════════════════════════════════════════════
NUM_CTX = {
    "arquitecto": _env_int("IA_NUM_CTX_ARQUITECTO",  8192),  # código largo
    "programador": _env_int("IA_NUM_CTX_PROGRAMADOR", 8192),  # código largo
    "vision":      _env_int("IA_NUM_CTX_VISION",      4096),  # visión VRAM intensiva
    "rapido":      _env_int("IA_NUM_CTX_RAPIDO",       4096),  # router ligero
}

NUM_BATCH = {
    "arquitecto": _env_int("IA_NUM_BATCH_ARQUITECTO",  512),  # balance VRAM/velocidad
    "programador": _env_int("IA_NUM_BATCH_PROGRAMADOR", 512),  # balance VRAM/velocidad
    "vision":      _env_int("IA_NUM_BATCH_VISION",      256),  # menor por VRAM vision
    "rapido":      _env_int("IA_NUM_BATCH_RAPIDO",      1024), # máximo throughput router
}


def ollama_options(
    model_key: str,
    temperature: float = 0.2,
    top_p: float = 0.9,
    num_predict: Optional[int] = None,
    keep_alive: Optional[str] = None,
) -> Dict[str, object]:
    """
    Opciones Ollama optimizadas para GTX 1080 Ti + i7-9700K.

    Flash Attention se activa con la variable de entorno OLLAMA_FLASH_ATTENTION=1
    (en el proceso de Ollama, NO aquí) y puede dar hasta 2-4× más velocidad
    en la fase de atención.
    """
    options: Dict[str, object] = {
        "num_gpu":    GPU_LAYERS.get(model_key, 20),
        "num_thread": CPU_THREADS,
        "num_ctx":    NUM_CTX.get(model_key, 4096),
        "num_batch":  NUM_BATCH.get(model_key, 512),
        "temperature": temperature,
        "top_p":       top_p,
        # f16_kv = True acelera KV cache en GPU (Pascal soporta FP16)
        "f16_kv": True,
        # low_vram = False → usa toda la VRAM disponible
        "low_vram": False,
        # mmap = True → mapea pesos a memoria, reduce RAM del host
        "use_mmap": True,
    }
    if num_predict is not None:
        options["num_predict"] = int(num_predict)
    if keep_alive is not None:
        options["keep_alive"] = keep_alive
    return options


# ═══════════════════════════════════════════════════════════════════════
#  PERFILES CONFIGURABLES
# ═══════════════════════════════════════════════════════════════════════
MODEL_PROFILES: Dict[str, Dict[str, Dict[str, object]]] = {
    "fast": {
        "models": {
            "arquitecto": "qwen2.5-coder:7b",
            "programador": "qwen2.5-coder:7b",
            "vision": "llava:7b",
        },
        "gpu_layers": {"arquitecto": 33, "programador": 33, "vision": 33},
    },
    "turbo": {
        "models": {
            "arquitecto": "qwen2.5-coder:14b",
            "programador": "qwen2.5-coder:7b",
            "vision": "llama3.2-vision:11b",
        },
        "gpu_layers": {"arquitecto": 35, "programador": 33, "vision": 30},
    },
    "ultra": {
        # Máxima calidad, para uso exclusivo (no multiusuario)
        "models": {
            "arquitecto": "qwen2.5-coder:14b",
            "programador": "qwen2.5-coder:14b",
            "vision": "llama3.2-vision:11b",
        },
        "gpu_layers": {"arquitecto": 35, "programador": 35, "vision": 30},
    },
}


def _apply_model_overrides() -> None:
    profile = (os.getenv("IA_MODEL_PROFILE") or "").strip().lower()
    if profile in MODEL_PROFILES:
        desired = MODEL_PROFILES[profile]
        for key, value in (desired.get("models") or {}).items():
            if isinstance(value, str) and value.strip():
                MODELS[key] = value.strip()
        for key, value in (desired.get("gpu_layers") or {}).items():
            try:
                GPU_LAYERS[key] = int(value)  # type: ignore[arg-type]
            except Exception:
                pass
    for role in list(MODELS.keys()):
        env_model = os.getenv(f"IA_MODEL_{role.upper()}")
        if env_model and env_model.strip():
            MODELS[role] = env_model.strip()
        env_layers = os.getenv(f"IA_GPU_LAYERS_{role.upper()}")
        if env_layers and str(env_layers).strip():
            try:
                GPU_LAYERS[role] = int(str(env_layers).strip())
            except ValueError:
                pass


_apply_model_overrides()

OUTPUT_DIR = Path("./archivos_generados")
OUTPUT_DIR.mkdir(exist_ok=True)

_MODELS_CACHE: Dict[str, object] = {"ts": 0.0, "models": []}
_MODELS_CACHE_TTL_S = 60.0

_HTTP: Optional[requests.Session] = None

_OLLAMA_HEALTH: Dict[str, object] = {
    "ts": 0.0, "ok": False, "fail_count": 0, "next_retry_ts": 0.0,
}
_OLLAMA_OK_TTL_S = 2.0
_OLLAMA_FAIL_MIN_RETRY_S = 1.0
_OLLAMA_FAIL_MAX_RETRY_S = 15.0


def http_session() -> requests.Session:
    """Session singleton con keep-alive + pool de 32 conexiones."""
    global _HTTP
    if _HTTP is not None:
        return _HTTP
    s = requests.Session()
    try:
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=32, pool_maxsize=32, max_retries=0
        )
        s.mount("http://", adapter)
        s.mount("https://", adapter)
    except Exception:
        pass
    _HTTP = s
    return s


def _backoff_seconds(fail_count: int) -> float:
    delay = _OLLAMA_FAIL_MIN_RETRY_S * (2 ** max(0, min(6, fail_count - 1)))
    return float(min(_OLLAMA_FAIL_MAX_RETRY_S, delay))


def _ollama_health_request(timeout_s: float = 1.5) -> bool:
    s = http_session()
    try:
        r = s.get(f"{OLLAMA_HOST}/api/version", timeout=timeout_s)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    try:
        r = s.get(f"{OLLAMA_HOST}/api/tags", timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════

PROMPT_ARQUITECTO = """Eres un arquitecto de software experto.
Analiza código, detecta errores, optimiza y proporciona soluciones completas.
Responde con código funcional y completo cuando sea necesario. Explica tus decisiones técnicas.
Si la pregunta NO es técnica, responde de forma natural y concisa en texto, sin generar código."""

PROMPT_PROGRAMADOR = """Eres un programador experto.
Escribe código limpio, completo y funcional cuando se te pida explícitamente.
Incluye comentarios útiles y manejo de errores.
Si la pregunta NO pide código, responde en texto natural y directo sin generar scripts."""

PROMPT_VISION = """Eres un analista visual experto.
Analiza imágenes, código en capturas, diagramas y UI.
Proporciona análisis técnico detallado."""

PROMPT_CONVERSACIONAL = """Eres Nexo, un asistente IA inteligente, amigable y de uso público.

REGLAS ESTRICTAS:
- Responde SIEMPRE en texto natural, en prosa clara y directa.
- NUNCA generes bloques de código Python, JavaScript ni ningún otro lenguaje de programación a menos que el usuario lo pida EXPLÍCITAMENTE usando palabras como "escribe código", "dame un script", "programa", etc.
- Para preguntas históricas, geográficas, culturales, de trivia o generales: responde directamente con la información solicitada en texto.
- Para saludos y charla casual: responde de forma breve y natural como una persona.
- NO sugieras instalar librerías ni ejecutar scripts cuando el usuario solo quiere información.
- Si no sabes algo con certeza, dilo honestamente en lugar de inventar o generar código."""


def identity_prefix() -> str:
    enabled = (os.getenv("NEXO_IDENTITY_GUARD") or "").strip().lower() in {
        "1", "true", "yes", "si", "sí", "on"
    }
    name = (os.getenv("NEXO_IDENTITY_NAME") or "").strip()
    if not enabled or not name:
        return ""
    return (
        f"Identidad fija: te llamas {name}. Eres una IA local creada y personalizada en este proyecto. "
        "No digas que perteneces a ningún proveedor externo ni uses otra identidad. "
        f"Si te preguntan cómo te llamas, responde claramente: 'Soy {name}'. "
        f"Tu nombre visible y permanente es {name}."
    )


_ID_PREFIX = identity_prefix()
if _ID_PREFIX:
    PROMPT_ARQUITECTO     = _ID_PREFIX + "\n\n" + PROMPT_ARQUITECTO
    PROMPT_PROGRAMADOR    = _ID_PREFIX + "\n\n" + PROMPT_PROGRAMADOR
    PROMPT_VISION         = _ID_PREFIX + "\n\n" + PROMPT_VISION
    PROMPT_CONVERSACIONAL = _ID_PREFIX + "\n\n" + PROMPT_CONVERSACIONAL


def print_banner():
    print(Fore.CYAN + Style.BRIGHT + f"""
╔══════════════════════════════════════════════════════════════════════╗
║   NEXO ORCHESTRATOR — ULTRA RÁPIDO                                  ║
║   🧠 Arquitecto 14B · 🔨 Programador 7B · 👁️  Visión 11B            ║
║   ⚡ GTX 1080 Ti {GPU_LAYERS['arquitecto']}L · CPU {CPU_THREADS}T · FA=ON · Batch 512    ║
╚══════════════════════════════════════════════════════════════════════╝
""")

def ok(msg):    print(f"{Fore.GREEN}✅ {msg}")
def warn(msg):  print(f"{Fore.YELLOW}⚠️  {msg}")
def error(msg): print(f"{Fore.RED}❌ {msg}")
def info(msg):  print(f"{Fore.CYAN}ℹ️  {msg}")

def separator(char="─", width=70):
    print(Fore.CYAN + char * width)

def ask(prompt: str, default: str = "") -> str:
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print()
        return default

# ═══════════════════════════════════════════════════════════════════════
#  GESTIÓN DE OLLAMA
# ═══════════════════════════════════════════════════════════════════════

def is_ollama_running() -> bool:
    now = time.time()
    try:
        ts = float(_OLLAMA_HEALTH.get("ts") or 0.0)
        cached_ok = bool(_OLLAMA_HEALTH.get("ok"))
        next_retry = float(_OLLAMA_HEALTH.get("next_retry_ts") or 0.0)
        if cached_ok and (now - ts) < _OLLAMA_OK_TTL_S:
            return True
        if (not cached_ok) and now < next_retry:
            return False
    except Exception:
        pass

    ok_now = _ollama_health_request(timeout_s=1.5)
    _OLLAMA_HEALTH["ts"] = now
    _OLLAMA_HEALTH["ok"] = ok_now
    if ok_now:
        _OLLAMA_HEALTH["fail_count"] = 0
        _OLLAMA_HEALTH["next_retry_ts"] = now
        return True

    try:
        fail_count = int(_OLLAMA_HEALTH.get("fail_count") or 0) + 1
    except Exception:
        fail_count = 1
    _OLLAMA_HEALTH["fail_count"] = fail_count
    _OLLAMA_HEALTH["next_retry_ts"] = now + _backoff_seconds(fail_count)
    return False


def start_ollama() -> bool:
    if is_ollama_running():
        ok("Ollama ya está corriendo")
        return True

    info("Iniciando Ollama con optimizaciones GPU...")
    ollama_cmd = "ollama"
    env = os.environ.copy()

    # ── Optimizaciones de entorno ────────────────────────────────────
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1")   # FlashAttention v2
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")      # Solo GTX 1080 Ti
    env.setdefault("OLLAMA_NUM_PARALLEL", "1")       # 1 req a la vez = max velocidad
    env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")  # Solo 1 modelo en VRAM
    # ──────────────────────────────────────────────────────────────────

    try:
        kwargs: Dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": env}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen([ollama_cmd, "serve"], **kwargs)

        pid_file = (
            os.getenv("NEXO_OLLAMA_PID_FILE") or os.getenv("IA_OLLAMA_PID_FILE") or ""
        ).strip()
        if pid_file:
            try:
                path = Path(pid_file).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "pid": int(proc.pid) if proc.pid else None,
                            "cmd": [ollama_cmd, "serve"],
                            "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                            "flash_attention": True,
                            "gpu_layers": GPU_LAYERS,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        for i in range(15):
            time.sleep(1)
            if _ollama_health_request(timeout_s=1.5):
                ok("Ollama iniciado con Flash Attention ⚡")
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
    now = time.time()
    try:
        cached_ts = float(_MODELS_CACHE.get("ts") or 0.0)
        cached_models = _MODELS_CACHE.get("models") or []
        if (now - cached_ts) < _MODELS_CACHE_TTL_S and isinstance(cached_models, list):
            return [str(x) for x in cached_models]
    except Exception:
        pass
    try:
        r = http_session().get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        _MODELS_CACHE["ts"] = now
        _MODELS_CACHE["models"] = models
        return models
    except Exception:
        return []


def is_model_installed(model_name: str) -> bool:
    target = model_name.lower()
    installed = [m.lower() for m in get_installed_models()]
    if ":" in target:
        return target in installed
    return any(m.split(":", 1)[0] == target for m in installed)


def pull_model(model_name: str) -> bool:
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
    info("Verificando modelos...")
    missing = []
    for role, model in MODELS.items():
        if is_model_installed(model):
            ok(f"{role}: {model}")
        else:
            error(f"{role}: {model} NO INSTALADO")
            missing.append((role, model))
    if missing:
        if ask("\n¿Descargar modelos faltantes? (s/n): ", default="n").lower() == "s":
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
    stream: bool = True,
    temperature: float = 0.2,
    top_p: float = 0.9,
) -> str:
    model = MODELS.get(model_key)
    if not model:
        error(f"Modelo '{model_key}' no definido")
        return ""

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user_msg: Dict = {"role": "user", "content": prompt}
    if images:
        user_msg["images"] = images
    messages.append(user_msg)

    payload = {
        "model":      model,
        "messages":   messages,
        "stream":     stream,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options":    ollama_options(model_key, temperature=temperature, top_p=top_p),
    }

    if stream:
        print(f"{Fore.GREEN}[{model_key.upper()}]: ", end="", flush=True)

    response_text = ""
    try:
        parts: List[str] = []
        with http_session().post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            stream=stream,
            timeout=(10, 300),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(chunk_size=8192, decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        if stream:
                            print(token, end="", flush=True)
                        parts.append(token)
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

        if stream:
            print()
        response_text = "".join(parts)
        return response_text

    except requests.exceptions.Timeout:
        error("\nTimeout - el modelo tardó demasiado")
        return response_text or ""
    except Exception as e:
        error(f"\nError en llamada a Ollama: {e}")
        return response_text or ""


# ═══════════════════════════════════════════════════════════════════════
#  EXTRACCIÓN Y GUARDADO DE CÓDIGO
# ═══════════════════════════════════════════════════════════════════════

def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    blocks = []
    for match in pattern.finditer(text):
        lang = match.group(1).lower() or "text"
        code = match.group(2)
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
            blocks.append({"lang": lang, "code": code, "extension": ext})
    return blocks


def save_code_blocks(blocks: List[Dict], base_name: str = "output") -> List[Path]:
    if not blocks:
        return []
    saved = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{Fore.CYAN}📁 {len(blocks)} bloque(s) de código detectado(s)")
    for i, block in enumerate(blocks, 1):
        preview = block["code"][:60].replace("\n", " ")
        print(f"  {i}. [{block['lang'].upper()}] {preview}...")
    choice = ask("\n¿Guardar? (s=todos / n=no / 1,2=específicos): ", default="n").lower()
    if choice == "n":
        return []
    if choice == "s":
        to_save = list(range(len(blocks)))
    else:
        to_save = []
        for num in choice.split(","):
            if num.strip().isdigit():
                idx = int(num.strip()) - 1
                if 0 <= idx < len(blocks):
                    to_save.append(idx)
    for idx in to_save:
        block = blocks[idx]
        default_name = f"{base_name}_{timestamp}{block['extension']}"
        name = ask(f"Nombre para archivo {idx+1} (Enter = {default_name}): ").strip()
        if not name:
            name = default_name
        elif not Path(name).suffix:
            name += block["extension"]
        filepath = OUTPUT_DIR / name
        filepath.write_text(block["code"], encoding="utf-8")
        ok(f"Guardado: {filepath}")
        saved.append(filepath)
    return saved


# ═══════════════════════════════════════════════════════════════════════
#  PROCESAMIENTO DE IMÁGENES
# ═══════════════════════════════════════════════════════════════════════

def load_image_base64(path: str) -> Tuple[Optional[str], Optional[str]]:
    if path.startswith("http://") or path.startswith("https://"):
        try:
            resp = http_session().get(path, timeout=15)
            resp.raise_for_status()
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            data = base64.b64encode(resp.content).decode()
            return data, mime
        except Exception as e:
            error(f"Error descargando imagen: {e}")
            return None, None
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
    separator()
    print(f"{Fore.MAGENTA}🔨 PIPELINE DE CÓDIGO (ULTRA)")
    separator()
    info("Fase 1/2: Generando código...")
    codigo_inicial = call_ollama("programador", prompt, system=PROMPT_PROGRAMADOR)
    if not codigo_inicial.strip():
        error("No se generó código")
        return ""
    info("\nFase 2/2: Revisión por arquitecto...")
    prompt_revision = (
        f"Solicitud original: {prompt}\n\nCódigo generado:\n```\n{codigo_inicial}\n```\n\n"
        "Revisa, corrige y mejora este código. Proporciona la versión final optimizada."
    )
    codigo_final = call_ollama("arquitecto", prompt_revision, system=PROMPT_ARQUITECTO)
    separator()
    ok("Pipeline completado")
    blocks = extract_code_blocks(codigo_final)
    if blocks:
        save_code_blocks(blocks, base_name="codigo")
    return codigo_final


def pipeline_vision(prompt: str, image_path: str) -> str:
    separator()
    print(f"{Fore.MAGENTA}👁️  PIPELINE DE VISIÓN")
    separator()
    info(f"Cargando imagen: {image_path}")
    img_data, mime = load_image_base64(image_path)
    if not img_data:
        return ""
    if not is_model_installed(MODELS["vision"]):
        warn("Modelo de visión no instalado")
        if ask("¿Descargar ahora? (s/n): ", default="n").lower() == "s":
            if not pull_model(MODELS["vision"]):
                return ""
        else:
            return ""
    info("Analizando imagen...")
    resultado = call_ollama("vision", prompt, system=PROMPT_VISION, images=[img_data])
    separator()
    ok("Análisis completado")
    return resultado


def pipeline_simple(prompt: str) -> str:
    return call_ollama("arquitecto", prompt, system=PROMPT_ARQUITECTO)


def pipeline_conversacional(prompt: str, stream: bool = False) -> str:
    return call_ollama("programador", prompt, system=PROMPT_CONVERSACIONAL, stream=stream)


# ═══════════════════════════════════════════════════════════════════════
#  DETECCIÓN DE INTENCIÓN
# ═══════════════════════════════════════════════════════════════════════

def _normalize_intent_text(text: str) -> str:
    base = " ".join(text.strip().lower().split())
    base = "".join(
        ch for ch in unicodedata.normalize("NFKD", base) if not unicodedata.combining(ch)
    )
    base = re.sub(r"[^\w\s]", " ", base, flags=re.UNICODE)
    return " ".join(base.split())


def is_greeting_or_smalltalk(user_input: str) -> bool:
    normalized = _normalize_intent_text(user_input)
    if not normalized:
        return True
    casual = {
        "hola", "holaa", "holaaa", "buenas", "buen dia", "buenos dias", "buenas tardes",
        "buenas noches", "hey", "hi", "hello", "que tal", "como estas", "como estás",
        "como va", "que pasa", "gracias", "muchas gracias", "ok", "vale", "perfecto",
        "jaja", "jeje", "xd", "jajaja", "lol", "adios", "adiós", "chao", "hasta luego",
        "nos vemos",
    }
    if normalized in casual:
        return True
    words = normalized.split()
    if "y tu" in normalized or normalized.startswith("y tu"):
        return True
    if len(words) <= 4 and not re.search(r"[?¿!¡]", user_input):
        return True
    return False


def is_code_request(user_input: str) -> bool:
    if is_greeting_or_smalltalk(user_input):
        return False
    text = user_input.lower()
    strong_markers = [
        "```", "traceback", "stack trace", "exception", "error:", "bug", "debug",
        "python", "javascript", "typescript", "node", "react", "html", "css", "sql",
        "docker", "git", ".py", ".js", ".ts", ".json", ".yml", ".yaml",
    ]
    if any(m in text for m in strong_markers):
        return True
    action_verbs = ["implementa", "escribe", "programa", "crea", "genera", "haz"]
    code_nouns = [
        "código", "codigo", "script", "función", "funcion", "clase", "api",
        "endpoint", "algoritmo",
    ]
    if any(v in text for v in action_verbs) and any(n in text for n in code_nouns):
        return True
    if re.search(
        r"\b(def|class|import|from|function|const|let|var|SELECT|INSERT|UPDATE)\b", user_input
    ):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════
#  CHAT INTERACTIVO
# ═══════════════════════════════════════════════════════════════════════

def chat_interactivo():
    print(f"\n{Fore.CYAN}💬 CHAT INTERACTIVO ⚡ (GPU optimizado)")
    print("Comandos: /codigo, /imagen <ruta>, /salir")
    separator()

    def _print_full_response(model_key: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        print(f"{Fore.GREEN}[{model_key.upper()}]: {text}", flush=True)

    while True:
        try:
            user_input = input(f"\n{Fore.WHITE}Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input:
            continue
        if user_input.lower() in ["/salir", "salir", "exit", "quit"]:
            break
        if user_input.startswith("/codigo"):
            prompt = user_input[7:].strip()
            if prompt:
                pipeline_codigo(prompt)
            else:
                warn("Uso: /codigo <descripción>")
            continue
        if user_input.startswith("/imagen"):
            parts = user_input[7:].strip().split(maxsplit=1)
            if len(parts) >= 1:
                image_path = parts[0]
                question = parts[1] if len(parts) > 1 else "Analiza esta imagen"
                pipeline_vision(question, image_path)
            else:
                warn("Uso: /imagen <ruta> [pregunta]")
            continue
        if is_greeting_or_smalltalk(user_input):
            stream = len(user_input.strip().split()) > 18
            resp = pipeline_conversacional(user_input, stream=stream)
            if not stream:
                _print_full_response("programador", resp)
            continue
        if is_code_request(user_input):
            pipeline_codigo(user_input)
            continue
        pipeline_simple(user_input)


# ═══════════════════════════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

def menu():
    print_banner()
    if not is_ollama_running():
        if not start_ollama():
            return
    ensure_models()
    opciones = {
        "1": ("💬 Chat interactivo", chat_interactivo),
        "2": ("🔨 Generar código", lambda: pipeline_codigo(ask("Describe el código a generar: "))),
        "3": ("👁️  Analizar imagen", lambda: pipeline_vision(
            ask("¿Qué analizar?: "), ask("Ruta de imagen: ")
        )),
        "4": ("📊 Ver modelos instalados", lambda: print(
            "\n".join(f"  • {m}" for m in get_installed_models())
        )),
        "5": ("📥 Descargar modelos", ensure_models),
        "6": ("⚡ Ver config GPU actual", lambda: print(
            f"\n  GPU Layers  : {GPU_LAYERS}"
            f"\n  CPU Threads : {CPU_THREADS}"
            f"\n  NUM_CTX     : {NUM_CTX}"
            f"\n  NUM_BATCH   : {NUM_BATCH}"
            f"\n  Keep alive  : {OLLAMA_KEEP_ALIVE}"
            f"\n  Flash Attn  : {os.getenv('OLLAMA_FLASH_ATTENTION','0')}"
        )),
        "0": ("❌ Salir", None),
    }
    while True:
        separator()
        print(f"{Fore.CYAN}MENÚ PRINCIPAL ─ ULTRA RÁPIDO ⚡")
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


def main():
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
            print("""
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
