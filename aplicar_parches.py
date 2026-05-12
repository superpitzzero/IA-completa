#!/usr/bin/env python3
"""
Script de corrección automática para NEXO
Aplica los parches críticos de rendimiento
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

def backup_file(path: Path) -> Path:
    """Crea backup del archivo con timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".backup_{timestamp}{path.suffix}")
    shutil.copy2(path, backup_path)
    print(f"✅ Backup creado: {backup_path.name}")
    return backup_path

def patch_orchestrator(path: Path) -> bool:
    """Aplica correcciones a orchestrator.py"""
    print("\n🔧 Parcheando orchestrator.py...")
    
    content = path.read_text(encoding="utf-8")
    original = content
    
    # PATCH 1: Aumentar GPU_LAYERS
    content = re.sub(
        r'GPU_LAYERS\s*=\s*\{[^}]+\}',
        '''GPU_LAYERS = {
    "arquitecto": 24,   # Optimizado para GTX 1080 Ti (11 GB VRAM)
    "programador": 22,  # Aumentado para mejor rendimiento
    "vision": 26,       # Aumentado para mejor rendimiento
}''',
        content,
        flags=re.DOTALL
    )
    
    # PATCH 2: Añadir keep_alive al payload
    # Buscar el payload y añadir keep_alive si no existe
    if '"keep_alive"' not in content:
        content = re.sub(
            r'(payload\s*=\s*\{[^}]*"stream":\s*stream,)',
            r'\1\n        "keep_alive": "10m",  # Mantener modelo en memoria',
            content
        )
    
    if content != original:
        backup_file(path)
        path.write_text(content, encoding="utf-8")
        print("✅ orchestrator.py parcheado correctamente")
        return True
    else:
        print("⚠️  orchestrator.py ya estaba actualizado o no se encontraron patrones")
        return False

def patch_web_app(path: Path) -> bool:
    """Aplica correcciones a web_app.py"""
    print("\n🔧 Parcheando web_app.py...")
    
    content = path.read_text(encoding="utf-8")
    original = content
    
    # PATCH 1: Desactivar búsqueda web por defecto
    # Buscar la función should_search_web y modificarla
    pattern = r'(def should_search_web\([^)]+\)[^:]*:)\s*\n(\s+)if attachment_context'
    replacement = r'''\1
    # PARCHE: Búsqueda web DESACTIVADA por defecto para mejor rendimiento
    # Para reactivar, comenta la línea siguiente y descomenta el código original
    return False
    
    # Código original (comentado):
    # \2if attachment_context'''
    
    content = re.sub(pattern, replacement, content)
    
    # PATCH 2: Cambiar modo por defecto a "rapido"
    content = re.sub(
        r'mode\s*=\s*str\([^)]+\.get\("mode",\s*"combinado"\)\)',
        'mode = str(payload.get("mode", "rapido"))  # PARCHE: modo rápido por defecto',
        content
    )
    
    content = re.sub(
        r'mode\s*=\s*str\(request\.form\.get\("mode",\s*"combinado"\)\)',
        'mode = str(request.form.get("mode", "rapido"))  # PARCHE: modo rápido por defecto',
        content
    )
    
    # PATCH 3: Streaming visible en programador (modo combinado)
    # Este es más complejo, solo añadimos un comentario sugerencia
    if 'draft = ollama_chat(' in content and '# PARCHE SUGERIDO' not in content:
        content = re.sub(
            r'(\s+yield event\(\{"type": "status", "message": "Ollama generando borrador\.\.\."\}\))\s*\n(\s+)(draft = ollama_chat\()',
            r'''\1
    # PARCHE SUGERIDO: Cambiar ollama_chat a ollama_chat_stream para feedback visual
    # Ver CORRECCIONES_URGENTES.md para implementación completa
\2\3''',
            content
        )
    
    if content != original:
        backup_file(path)
        path.write_text(content, encoding="utf-8")
        print("✅ web_app.py parcheado correctamente")
        return True
    else:
        print("⚠️  web_app.py ya estaba actualizado o no se encontraron patrones")
        return False

def verify_files(root: Path):
    """Verifica que los archivos existen"""
    orchestrator = root / "orchestrator.py"
    web_app = root / "web_app.py"
    
    if not orchestrator.exists():
        print(f"❌ No se encontró orchestrator.py en {root}")
        return None, None
    
    if not web_app.exists():
        print(f"❌ No se encontró web_app.py en {root}")
        return None, None
    
    return orchestrator, web_app

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          PARCHES AUTOMÁTICOS - NEXO                          ║
║  Corrige problemas de velocidad y rendimiento                        ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    # Detectar directorio raíz
    root = Path.cwd()
    
    # Verificar archivos
    orchestrator_path, web_app_path = verify_files(root)
    if not orchestrator_path or not web_app_path:
        print("\n⚠️  Asegúrate de ejecutar este script desde el directorio del proyecto")
        print(f"   Directorio actual: {root}")
        return 1
    
    print(f"📁 Directorio del proyecto: {root}")
    print(f"📄 Archivos encontrados:")
    print(f"   - orchestrator.py")
    print(f"   - web_app.py")
    
    # Confirmar antes de aplicar
    print("\n⚠️  Este script va a:")
    print("   1. Crear backups de los archivos originales")
    print("   2. Desactivar búsqueda web automática (mejora velocidad)")
    print("   3. Cambiar modo por defecto a 'rápido'")
    print("   4. Optimizar GPU_LAYERS para GTX 1080 Ti")
    print("   5. Añadir keep_alive para mantener modelos en memoria")
    
    response = input("\n¿Continuar? (s/N): ").strip().lower()
    if response not in ('s', 'si', 'sí', 'yes', 'y'):
        print("❌ Cancelado por el usuario")
        return 0
    
    # Aplicar parches
    patched_count = 0
    
    if patch_orchestrator(orchestrator_path):
        patched_count += 1
    
    if patch_web_app(web_app_path):
        patched_count += 1
    
    # Resumen
    print("\n" + "="*70)
    print(f"✅ Proceso completado: {patched_count} archivo(s) parcheado(s)")
    print("="*70)
    
    if patched_count > 0:
        print("\n📋 PRÓXIMOS PASOS:")
        print("   1. Reinicia la aplicación web:")
        print("      > LANZAR_TODO_WEB.bat")
        print("   2. Prueba un mensaje simple para verificar velocidad")
        print("   3. Verifica que nvidia-smi muestre uso de GPU")
        print("\n💡 REVERTIR CAMBIOS:")
        print("   Los backups están en el mismo directorio con sufijo .backup_*")
        print("   Renombra el backup original para restaurar")
    
    print("\n📖 Para más información, lee: CORRECCIONES_URGENTES.md")
    
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
