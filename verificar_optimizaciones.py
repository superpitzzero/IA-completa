#!/usr/bin/env python3
"""
VERIFICADOR DE OPTIMIZACIONES
==============================

Script para verificar que las optimizaciones están correctamente aplicadas.

USO:
    python verificar_optimizaciones.py
"""

import sys
from pathlib import Path


def verificar_orchestrator(ruta: Path) -> tuple[bool, list[str]]:
    """Verifica que orchestrator.py está correctamente optimizado."""
    errores = []
    
    if not ruta.exists():
        return False, [f"❌ No se encuentra {ruta}"]
    
    contenido = ruta.read_text(encoding='utf-8')
    
    # Verificar que tiene los nombres correctos de modelos
    if '"arquitecto":' not in contenido or '"programador":' not in contenido:
        errores.append("❌ Falta configuración de modelos 'arquitecto' y 'programador'")
    
    if '"principal":' in contenido or '"alternativo":' in contenido:
        errores.append("❌ CRÍTICO: Usa nombres incorrectos 'principal'/'alternativo' - usa orchestrator_optimizado_CORRECTO.py")
    
    # Verificar OLLAMA_KEEP_ALIVE
    if 'OLLAMA_KEEP_ALIVE' in contenido:
        if '"1m"' in contenido or "'1m'" in contenido:
            print("  ✅ OLLAMA_KEEP_ALIVE optimizado (1m)")
        elif '"45m"' in contenido or "'45m'" in contenido:
            errores.append("⚠️  OLLAMA_KEEP_ALIVE sin optimizar (45m) - debería ser 1m")
    
    # Verificar GPU_LAYERS
    if 'GPU_LAYERS' in contenido:
        if '"arquitecto": 20' in contenido or "'arquitecto': 20" in contenido:
            print("  ✅ GPU_LAYERS optimizado (20/18/22)")
        elif '"arquitecto": 24' in contenido or "'arquitecto': 24" in contenido:
            errores.append("⚠️  GPU_LAYERS sin optimizar (24/22/26) - debería ser 20/18/22")
    
    # Verificar que tiene el parámetro keep_alive en ollama_options
    if 'def ollama_options' in contenido:
        if 'keep_alive: Optional[str]' in contenido or 'keep_alive:' in contenido:
            print("  ✅ ollama_options soporta keep_alive personalizado")
        else:
            errores.append("⚠️  ollama_options no soporta keep_alive - falta optimización")
    
    # Verificar número de líneas aproximado
    lineas = len(contenido.split('\n'))
    if lineas < 900:
        errores.append(f"❌ CRÍTICO: Archivo muy corto ({lineas} líneas) - probablemente es la versión incorrecta")
        errores.append("   Usa orchestrator_optimizado_CORRECTO.py que tiene ~1018 líneas")
    elif lineas > 950:
        print(f"  ✅ Tamaño correcto ({lineas} líneas)")
    
    return len(errores) == 0, errores


def verificar_web_app(ruta: Path) -> tuple[bool, list[str]]:
    """Verifica que web_app.py tiene las optimizaciones."""
    errores = []
    
    if not ruta.exists():
        return False, [f"❌ No se encuentra {ruta}"]
    
    contenido = ruta.read_text(encoding='utf-8')
    
    # Verificar funciones de optimización
    if 'def unload_ollama_model' in contenido:
        print("  ✅ Función unload_ollama_model presente")
    else:
        errores.append("❌ Falta función unload_ollama_model - ejecutar aplicar_optimizaciones_automatico.py")
    
    if 'def unload_all_ollama_models_except' in contenido:
        print("  ✅ Función unload_all_ollama_models_except presente")
    else:
        errores.append("❌ Falta función unload_all_ollama_models_except")
    
    if 'def ollama_payload_optimized' in contenido:
        print("  ✅ Función ollama_payload_optimized presente")
    else:
        errores.append("❌ Falta función ollama_payload_optimized")
    
    # Verificar stream_ollama_answer optimizado
    if 'VERSIÓN OPTIMIZADA' in contenido or 'unload_ollama_model(model_name)' in contenido:
        print("  ✅ stream_ollama_answer optimizado")
    else:
        errores.append("⚠️  stream_ollama_answer no parece optimizado")
    
    return len(errores) == 0, errores


def main():
    """Función principal de verificación."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║       VERIFICADOR DE OPTIMIZACIONES DE MEMORIA               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    
    todo_ok = True
    
    # Verificar orchestrator.py
    print("📋 Verificando orchestrator.py...")
    ok, errores = verificar_orchestrator(Path('orchestrator.py'))
    if not ok:
        todo_ok = False
        for error in errores:
            print(f"  {error}")
    print()
    
    # Verificar web_app.py
    print("📋 Verificando web_app.py...")
    ok, errores = verificar_web_app(Path('web_app.py'))
    if not ok:
        todo_ok = False
        for error in errores:
            print(f"  {error}")
    print()
    
    # Verificar web_app_optimizado.py (opcional)
    if Path('web_app_optimizado.py').exists():
        print("📋 Verificando web_app_optimizado.py...")
        ok, errores = verificar_web_app(Path('web_app_optimizado.py'))
        if not ok:
            for error in errores:
                print(f"  {error}")
        print()
    
    # Verificar backups
    print("📋 Verificando backups...")
    archivos_backup = [
        'orchestrator.py.backup_original',
        'orchestrator.py.backup',
        'web_app.py.backup_original',
        'web_app.py.backup_optimizacion',
    ]
    backups_encontrados = [b for b in archivos_backup if Path(b).exists()]
    if backups_encontrados:
        print(f"  ✅ Backups encontrados: {', '.join(backups_encontrados)}")
    else:
        print("  ⚠️  No se encontraron archivos de backup")
    print()
    
    # Resumen final
    print("═" * 65)
    if todo_ok:
        print("✅ ¡TODO CORRECTO! Las optimizaciones están aplicadas.")
        print()
        print("PRÓXIMOS PASOS:")
        print("  1. Si aún no lo hiciste, reemplaza web_app.py:")
        print("     cp web_app_optimizado.py web_app.py")
        print("  2. Reinicia la aplicación web")
        print("  3. Verifica el uso de VRAM con: nvidia-smi")
    else:
        print("❌ HAY PROBLEMAS - Revisa los errores arriba")
        print()
        print("SOLUCIONES:")
        print("  1. Para orchestrator.py:")
        print("     cp orchestrator_optimizado_CORRECTO.py orchestrator.py")
        print("  2. Para web_app.py:")
        print("     python aplicar_optimizaciones_automatico.py web_app.py")
    print("═" * 65)


if __name__ == "__main__":
    main()
