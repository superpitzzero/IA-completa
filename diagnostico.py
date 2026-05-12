#!/usr/bin/env python3
"""
Script de diagnóstico para NEXO
Identifica problemas de rendimiento y configuración
"""

import json
import time
import subprocess
import sys
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


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


# region agent log
def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "e42fd3",
            "runId": os.getenv("AGENT_RUN_ID", "pre-fix"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
            "id": "log_"
            + str(int(time.time() * 1000))
            + "_"
            + hashlib.sha1(f"{location}|{message}".encode("utf-8", errors="ignore")).hexdigest()[:10],
        }
        Path("debug-e42fd3.log").open("a", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )
    except Exception:
        pass


_agent_log(
    "H-ENC-1",
    "diagnostico.py:configure_console_encoding",
    "Configured console encoding (best-effort)",
    {"python": sys.version.split()[0], "platform": sys.platform},
)
# endregion agent log

try:
    import requests
except ImportError:
    print("❌ Falta la librería 'requests'")
    print("   Instala con: pip install requests")
    sys.exit(1)

OLLAMA_HOST = "http://localhost:11434"

def print_section(title: str):
    """Imprime sección con formato"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def check_ollama_running() -> bool:
    """Verifica si Ollama está corriendo"""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return r.status_code == 200
    except:
        return False

def get_loaded_models() -> list:
    """Obtiene modelos cargados en memoria"""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/ps", timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("models", [])
    except:
        return []

def get_installed_models() -> list:
    """Obtiene modelos instalados"""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
        return r.json().get("models", [])
    except:
        return []

def test_model_speed(model: str) -> Optional[float]:
    """Prueba velocidad de un modelo"""
    print(f"\n🧪 Probando velocidad de {model}...")
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Di solo 'OK'"}],
        "stream": False,
        "options": {"num_predict": 10}
    }
    
    try:
        start = time.time()
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=60)
        elapsed = time.time() - start
        
        if r.status_code == 200:
            print(f"   ✅ Respondió en {elapsed:.2f} segundos")
            return elapsed
        else:
            print(f"   ❌ Error {r.status_code}")
            return None
    except requests.Timeout:
        print(f"   ❌ Timeout (>60s)")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def check_gpu_available() -> bool:
    """Verifica si hay GPU disponible"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"   GPU detectada: {result.stdout.strip()}")
            return True
    except:
        pass
    return False

def check_gpu_usage() -> Optional[str]:
    """Verifica uso actual de GPU"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Sin procesos usando GPU"
    except:
        return None

def format_bytes(bytes_val: int) -> str:
    """Formatea bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              DIAGNÓSTICO - NEXO                              ║
║  Identifica problemas de rendimiento                                 ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    # 1. Verificar Ollama
    print_section("1. OLLAMA")
    
    if not check_ollama_running():
        print("❌ Ollama NO está corriendo")
        print("\n💡 Solución:")
        print("   1. Abre una terminal y ejecuta: ollama serve")
        print("   2. O reinicia el sistema")
        return 1
    
    print("✅ Ollama está corriendo")
    
    # 2. Verificar GPU
    print_section("2. GPU / NVIDIA")
    
    if not check_gpu_available():
        print("❌ No se detectó GPU NVIDIA o nvidia-smi no está disponible")
        print("\n⚠️  ADVERTENCIA: Sin GPU, los modelos serán EXTREMADAMENTE lentos")
        print("\n💡 Solución:")
        print("   1. Instala drivers NVIDIA actualizados")
        print("   2. Verifica que la GPU está habilitada en BIOS")
    else:
        print("✅ GPU NVIDIA disponible")
        
        usage = check_gpu_usage()
        if usage:
            print(f"\n📊 Procesos usando GPU:")
            if "Sin procesos" in usage:
                print(f"   {usage}")
                print("   ⚠️  Ollama no está usando la GPU - revisa configuración")
            else:
                for line in usage.split('\n'):
                    print(f"   {line}")
    
    # 3. Verificar modelos instalados
    print_section("3. MODELOS INSTALADOS")
    
    installed = get_installed_models()
    if not installed:
        print("❌ No hay modelos instalados")
        print("\n💡 Solución:")
        print("   ollama pull qwen2.5-coder:14b")
        print("   ollama pull qwen2.5-coder:7b")
        return 1
    
    required_models = ["qwen2.5-coder:14b", "qwen2.5-coder:7b"]
    found_models = {m["name"].lower(): m for m in installed}
    
    for model_name in required_models:
        model_key = model_name.lower()
        if model_key in found_models:
            model = found_models[model_key]
            size = model.get("size", 0)
            print(f"✅ {model_name} - {format_bytes(size)}")
        else:
            print(f"❌ {model_name} NO instalado")
            print(f"   Instala con: ollama pull {model_name}")
    
    # 4. Verificar modelos en memoria
    print_section("4. MODELOS CARGADOS EN MEMORIA")
    
    loaded = get_loaded_models()
    if not loaded:
        print("⚠️  No hay modelos cargados en memoria")
        print("   (Esto es normal si no has usado Ollama recientemente)")
    else:
        for model in loaded:
            name = model.get("name", "unknown")
            size_vram = model.get("size_vram", 0)
            print(f"✅ {name}")
            print(f"   VRAM: {format_bytes(size_vram)}")
            
            # Calcular tiempo desde que se cargó
            expires_at = model.get("expires_at", "")
            if expires_at:
                print(f"   Expira: {expires_at}")
    
    # 5. Test de velocidad
    print_section("5. TEST DE VELOCIDAD")
    
    print("Este test mide el tiempo de respuesta de los modelos principales.")
    print("⚠️  Si es la primera vez, puede tardar más (carga inicial).")
    
    response = input("\n¿Ejecutar test de velocidad? (s/N): ").strip().lower()
    if response not in ('s', 'si', 'sí', 'yes', 'y'):
        print("⏭️  Test de velocidad omitido")
    else:
        speeds = {}
        
        # Test programador (7B)
        if "qwen2.5-coder:7b" in [m["name"].lower() for m in installed]:
            elapsed = test_model_speed("qwen2.5-coder:7b")
            if elapsed:
                speeds["7b"] = elapsed
        
        # Test arquitecto (14B)
        if "qwen2.5-coder:14b" in [m["name"].lower() for m in installed]:
            elapsed = test_model_speed("qwen2.5-coder:14b")
            if elapsed:
                speeds["14b"] = elapsed
        
        # Análisis
        if speeds:
            print("\n📊 RESULTADOS:")
            for model, elapsed in speeds.items():
                status = "🟢 Excelente" if elapsed < 5 else "🟡 Aceptable" if elapsed < 15 else "🔴 Lento"
                print(f"   {model}: {elapsed:.2f}s - {status}")
            
            if any(t > 20 for t in speeds.values()):
                print("\n⚠️  ADVERTENCIA: Respuestas muy lentas detectadas")
                print("\n💡 Posibles causas:")
                print("   1. GPU no está siendo utilizada")
                print("   2. GPU_LAYERS demasiado bajo (mucho offload a RAM)")
                print("   3. Poca RAM disponible (sistema haciendo swap)")
                print("   4. CPU/GPU con carga alta de otros programas")
        else:
            print("\n❌ No se pudo completar el test de velocidad")
    
    # 6. Verificar archivos de configuración
    print_section("6. ARCHIVOS DE CONFIGURACIÓN")
    
    root = Path.cwd()
    
    files_to_check = [
        ("orchestrator.py", True),
        ("web_app.py", True),
        ("web_data/settings.json", False),
        ("logs/web_app.log", False),
        ("logs/cloudflared.log", False),
    ]
    
    for filename, required in files_to_check:
        path = root / filename
        if path.exists():
            size = path.stat().st_size
            print(f"✅ {filename} - {format_bytes(size)}")
        else:
            marker = "❌" if required else "⚠️ "
            print(f"{marker} {filename} NO encontrado")
    
    # 7. Leer configuración GPU_LAYERS si existe
    orchestrator_path = root / "orchestrator.py"
    if orchestrator_path.exists():
        print("\n📋 Configuración GPU_LAYERS detectada:")
        content = orchestrator_path.read_text(encoding="utf-8")
        
        # Buscar GPU_LAYERS
        import re
        match = re.search(r'GPU_LAYERS\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if match:
            gpu_config = match.group(1)
            for line in gpu_config.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    print(f"   {line}")
        
        # Buscar keep_alive
        if '"keep_alive"' in content or "'keep_alive'" in content:
            print("   ✅ keep_alive configurado")
        else:
            print("   ⚠️  keep_alive NO configurado (modelos se descargan rápido)")
    
    # 8. Resumen y recomendaciones
    print_section("8. RESUMEN Y RECOMENDACIONES")
    
    issues = []
    
    if not check_ollama_running():
        issues.append("Ollama no está corriendo")
    
    if not check_gpu_available():
        issues.append("GPU no detectada o no disponible")
    
    required_count = sum(1 for m in required_models if m.lower() in [x["name"].lower() for x in installed])
    if required_count < len(required_models):
        issues.append(f"Faltan {len(required_models) - required_count} modelos requeridos")
    
    if issues:
        print("❌ PROBLEMAS DETECTADOS:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\n💡 Lee CORRECCIONES_URGENTES.md para soluciones detalladas")
    else:
        print("✅ Configuración básica correcta")
        print("\n💡 Si aún experimentas lentitud:")
        print("   1. Ejecuta: python aplicar_parches.py")
        print("   2. Lee: CORRECCIONES_URGENTES.md")
        print("   3. Verifica que GPU esté siendo utilizada (nvidia-smi)")
    
    print("\n" + "="*70)
    print("Diagnóstico completado")
    print("="*70)
    
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado por el usuario")
        exit(130)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
