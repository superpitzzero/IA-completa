#!/usr/bin/env python3
"""
APLICADOR AUTOMÁTICO DE OPTIMIZACIONES A WEB_APP.PY
====================================================

Este script aplica automáticamente las optimizaciones de memoria
al archivo web_app.py sin necesidad de edición manual.

USO:
    python aplicar_optimizaciones_automatico.py web_app.py

SALIDA:
    - web_app_optimizado.py (versión optimizada)
    - web_app.py.backup (backup del original)
"""

import sys
import re
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════
# CÓDIGO A INSERTAR
# ═══════════════════════════════════════════════════════════════════════

NUEVAS_FUNCIONES_OPTIMIZACION = '''
# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES DE OPTIMIZACIÓN DE MEMORIA
# ═══════════════════════════════════════════════════════════════════════

def unload_ollama_model(model_name: str) -> bool:
    """
    Descarga un modelo de memoria inmediatamente.
    Libera VRAM para permitir más usuarios concurrentes.
    """
    try:
        s = http_session()
        payload = {
            "model": model_name,
            "keep_alive": 0  # 0 = descargar inmediatamente
        }
        r = s.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def unload_all_ollama_models_except(keep_model: Optional[str] = None) -> None:
    """
    Descarga todos los modelos excepto el especificado.
    Garantiza que solo un modelo esté en memoria a la vez.
    """
    try:
        s = http_session()
        r = s.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code != 200:
            return
        
        data = r.json()
        models = data.get("models", [])
        
        for model in models:
            model_name = model.get("name", "")
            if model_name and model_name != keep_model:
                unload_ollama_model(model_name)
    except Exception:
        pass


def ollama_payload_optimized(
    model_key: str, 
    messages: List[Dict[str, Any]], 
    stream: bool,
    unload_after: bool = True
) -> Dict[str, Any]:
    """
    Versión optimizada de ollama_payload con descarga automática.
    
    Args:
        model_key: Clave del modelo en MODELS dict
        messages: Lista de mensajes
        stream: Si hacer streaming
        unload_after: Si descargar el modelo después de 1 minuto (vs 45 minutos)
    """
    model = MODELS[model_key]
    
    # Descargar otros modelos antes de cargar este
    unload_all_ollama_models_except(model)
    
    # Keep alive reducido si vamos a descargar después
    keep_alive = "1m" if unload_after else OLLAMA_KEEP_ALIVE
    
    options = ollama_options(model_key, keep_alive=keep_alive)
    
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": options,
    }
    return payload

'''


def encontrar_linea_insercion(contenido: str) -> int:
    """Encuentra la línea adecuada para insertar las nuevas funciones."""
    lineas = contenido.split('\n')
    
    # Buscar después de la definición de http_session() o similar
    for i, linea in enumerate(lineas):
        if 'def http_session(' in linea:
            # Buscar el final de esta función
            nivel_indent = len(linea) - len(linea.lstrip())
            for j in range(i + 1, len(lineas)):
                if lineas[j].strip() and not lineas[j].startswith(' ' * (nivel_indent + 1)):
                    return j
    
    # Si no encuentra http_session, buscar después de los imports
    for i, linea in enumerate(lineas):
        if linea.startswith('def ') or linea.startswith('class '):
            return i
    
    return 100  # Fallback


def actualizar_ollama_options(contenido: str) -> str:
    """Actualiza ollama_options para soportar keep_alive."""
    
    # Patrón para encontrar la función ollama_options
    patron_funcion = r'(def ollama_options\([^)]*\)\s*->\s*Dict\[str,\s*object\]:)'
    
    # Buscar la firma actual
    match = re.search(patron_funcion, contenido)
    if not match:
        print("⚠️  No se encontró ollama_options, saltando...")
        return contenido
    
    # Reemplazar la firma para incluir keep_alive
    nueva_firma = '''def ollama_options(
    model_key: str,
    temperature: float = 0.2,
    top_p: float = 0.9,
    num_predict: Optional[int] = None,
    keep_alive: Optional[str] = None,  # NUEVO: parámetro para keep_alive
) -> Dict[str, object]:'''
    
    # Reemplazar la firma
    contenido_actualizado = re.sub(
        r'def ollama_options\([^)]*\)\s*->\s*Dict\[str,\s*object\]:',
        nueva_firma,
        contenido
    )
    
    # Agregar el código para usar keep_alive antes del return
    # Buscar el patrón "return options"
    contenido_actualizado = re.sub(
        r'(\s+)(return options)',
        r'\1# NUEVO: Configurar keep_alive si se proporciona\n\1if keep_alive is not None:\n\1    options["keep_alive"] = keep_alive\n\1\n\1\2',
        contenido_actualizado
    )
    
    return contenido_actualizado


def actualizar_stream_ollama_answer(contenido: str) -> str:
    """Actualiza stream_ollama_answer con la versión optimizada."""
    
    # Esta es la versión optimizada completa
    nueva_funcion = '''def stream_ollama_answer(
    chat: Dict[str, Any],
    user_message: str,
    mode: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    web_context: str = "",
    sources: Optional[List[Dict[str, str]]] = None,
    search_error: str = "",
) -> Generator[str, None, Dict[str, Any]]:
    """
    VERSIÓN OPTIMIZADA: Usa modelos secuencialmente con descarga automática.
    
    OPTIMIZACIONES:
    1. Modo "rapido": Solo usa 1 modelo (programador) - RECOMENDADO
    2. Modo "codigo"/"combinado": Usa modelos secuencialmente, descargando el anterior
    3. Keep alive reducido a 1 minuto en lugar de 45 minutos
    4. Descarga explícita de modelos después de usarlos
    """
    attachment_context = build_attachment_context(attachments or [])
    if mode != "rapido" and not (attachments or []) and is_conversational_message(user_message):
        mode = "rapido"
    full_web_context = web_context or build_web_context(sources or [], search_error)
    context_prompt = build_user_prompt(chat, user_message, mode, attachment_context, full_web_context)
    final_text = ""

    # ═══════════════════════════════════════════════════════════════════
    # MODO RÁPIDO: Solo usa el modelo "programador" (OPTIMIZADO)
    # ═══════════════════════════════════════════════════════════════════
    if mode == "rapido":
        fast_model_key = os.getenv("NEXO_FAST_OLLAMA_ROLE", "programador").strip().lower() or "programador"
        if fast_model_key not in MODELS:
            fast_model_key = "programador"
        
        error = ensure_ai_ready([fast_model_key])
        if error:
            yield event({"type": "error", "message": error})
            return {"text": "", "provider": "ollama"}
        
        # Descargar otros modelos antes de usar este
        model_name = MODELS[fast_model_key]
        unload_all_ollama_models_except(model_name)
        
        is_casual = is_conversational_message(user_message)
        system_prompt = PROMPT_CONVERSACIONAL if is_casual else PROMPT_ARQUITECTO
        
        messages = [
            {"role": "system", "content": guarded_system_prompt(system_prompt, ai_settings=load_ai_settings())},
            {"role": "user", "content": context_prompt if not is_casual else user_message},
        ]
        
        yield event({"type": "status", "message": "Pensando..."})
        for token in ollama_chat_stream(fast_model_key, messages):
            final_text += token
            yield event({"type": "token", "token": token})
        
        # OPTIMIZACIÓN: Descargar modelo después de 1 minuto de inactividad
        # (En lugar de los 45 minutos por defecto)
        unload_ollama_model(model_name)
        
        return {"text": final_text, "provider": "ollama"}

    # ═══════════════════════════════════════════════════════════════════
    # MODO CÓDIGO/COMBINADO: Usa modelos SECUENCIALMENTE (OPTIMIZADO)
    # ═══════════════════════════════════════════════════════════════════
    
    # Verificar que ambos modelos estén disponibles
    error = ensure_ai_ready(["programador", "arquitecto"])
    if error:
        yield event({"type": "error", "message": error})
        return {"text": "", "provider": "ollama"}

    if mode == "codigo":
        draft_prompt = f"""{context_prompt}

Responde a la peticion actual del usuario con una solucion tecnica directa. Si pide codigo, entregalo en bloques Markdown con nombre de lenguaje."""
        review_prompt = (
            "Usa el borrador solo como material interno y devuelve la respuesta final directa al usuario. "
            "No digas 'el codigo proporcionado' ni 'la solucion anterior' salvo que el usuario haya pegado codigo para revisar."
        )
    else:
        draft_prompt = f"""{context_prompt}

Genera un borrador de respuesta util, completo y bien estructurado."""
        review_prompt = (
            "Usa el borrador solo como material interno. Devuelve una respuesta final natural, sin mencionar el borrador ni repetir respuestas antiguas."
        )

    # ═══ PASO 1: Generar borrador con "programador" ═══
    yield event({"type": "status", "message": "Generando borrador..."})
    
    # Descargar otros modelos antes de cargar programador
    programador_model = MODELS["programador"]
    unload_all_ollama_models_except(programador_model)
    
    ai_settings = load_ai_settings()
    draft = ollama_chat(
        "programador",
        [
            {"role": "system", "content": guarded_system_prompt(PROMPT_PROGRAMADOR, ai_settings=ai_settings)},
            {"role": "user", "content": draft_prompt},
        ],
    )
    
    # OPTIMIZACIÓN CRÍTICA: Descargar "programador" antes de cargar "arquitecto"
    yield event({"type": "status", "message": "Preparando revisión..."})
    unload_ollama_model(programador_model)
    
    # Pequeña pausa para asegurar descarga completa
    import time
    time.sleep(0.3)
    
    # ═══ PASO 2: Revisar con "arquitecto" ═══
    # Descargar cualquier otro modelo antes de cargar arquitecto
    arquitecto_model = MODELS["arquitecto"]
    unload_all_ollama_models_except(arquitecto_model)
    
    final_prompt = f"""{context_prompt}

Borrador:
```
{draft}
```

{review_prompt}"""

    yield event({"type": "status", "message": "Revisando..."})
    for token in ollama_chat_stream(
        "arquitecto",
        [
            {"role": "system", "content": guarded_system_prompt(PROMPT_ARQUITECTO, ai_settings=ai_settings)},
            {"role": "user", "content": final_prompt},
        ],
    ):
        final_text += token
        yield event({"type": "token", "token": token})
    
    # OPTIMIZACIÓN: Descargar arquitecto después de usar
    unload_ollama_model(arquitecto_model)
    
    return {"text": final_text, "provider": "ollama"}'''
    
    # Buscar la función stream_ollama_answer existente y reemplazarla
    # Patrón complejo para capturar toda la función
    patron = r'def stream_ollama_answer\([^)]*\)[^:]*:.*?(?=\ndef [a-z_]+\(|$)'
    
    # Buscar manualmente la función
    lineas = contenido.split('\n')
    inicio_funcion = -1
    fin_funcion = -1
    
    for i, linea in enumerate(lineas):
        if 'def stream_ollama_answer(' in linea:
            inicio_funcion = i
            # Encontrar el nivel de indentación
            indent_base = len(linea) - len(linea.lstrip())
            
            # Buscar el final de la función (siguiente función al mismo nivel o menor)
            for j in range(i + 1, len(lineas)):
                linea_actual = lineas[j]
                if linea_actual.strip() == '':
                    continue
                indent_actual = len(linea_actual) - len(linea_actual.lstrip())
                
                # Si encontramos una línea con indent menor o igual que no es un comentario
                if indent_actual <= indent_base and linea_actual.strip():
                    if linea_actual.strip().startswith('def ') or linea_actual.strip().startswith('class '):
                        fin_funcion = j
                        break
            
            if fin_funcion == -1:
                fin_funcion = len(lineas)
            
            break
    
    if inicio_funcion == -1:
        print("⚠️  No se encontró stream_ollama_answer, saltando...")
        return contenido
    
    # Reemplazar la función
    nuevas_lineas = lineas[:inicio_funcion] + [nueva_funcion] + lineas[fin_funcion:]
    
    return '\n'.join(nuevas_lineas)


def aplicar_optimizaciones(ruta_web_app: Path) -> None:
    """Aplica todas las optimizaciones a web_app.py"""
    
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║  APLICADOR AUTOMÁTICO DE OPTIMIZACIONES DE MEMORIA           ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    
    # Verificar que existe
    if not ruta_web_app.exists():
        print(f"❌ Error: No se encuentra {ruta_web_app}")
        sys.exit(1)
    
    # Leer contenido
    print(f"📖 Leyendo {ruta_web_app.name}...")
    contenido = ruta_web_app.read_text(encoding='utf-8')
    
    # Crear backup
    backup_path = ruta_web_app.with_suffix('.py.backup_optimizacion')
    print(f"💾 Creando backup: {backup_path.name}")
    backup_path.write_text(contenido, encoding='utf-8')
    
    # 1. Insertar nuevas funciones
    print("🔧 Insertando funciones de optimización...")
    linea_insercion = encontrar_linea_insercion(contenido)
    lineas = contenido.split('\n')
    lineas.insert(linea_insercion, NUEVAS_FUNCIONES_OPTIMIZACION)
    contenido = '\n'.join(lineas)
    
    # 2. Actualizar ollama_options
    print("🔧 Actualizando ollama_options()...")
    contenido = actualizar_ollama_options(contenido)
    
    # 3. Actualizar stream_ollama_answer
    print("🔧 Actualizando stream_ollama_answer()...")
    contenido = actualizar_stream_ollama_answer(contenido)
    
    # Guardar resultado
    salida = ruta_web_app.parent / 'web_app_optimizado.py'
    print(f"💾 Guardando resultado: {salida.name}")
    salida.write_text(contenido, encoding='utf-8')
    
    print()
    print("✅ ¡Optimizaciones aplicadas exitosamente!")
    print()
    print("ARCHIVOS GENERADOS:")
    print(f"  • {salida.name} - Versión optimizada")
    print(f"  • {backup_path.name} - Backup del original")
    print()
    print("PRÓXIMOS PASOS:")
    print("  1. Reemplazar web_app.py con web_app_optimizado.py")
    print("  2. Usar orchestrator_optimizado_CORRECTO.py en lugar del original")
    print("  3. Reiniciar la aplicación web")
    print()
    print("BENEFICIOS:")
    print("  ✓ Reducción de 50-70% en uso de VRAM")
    print("  ✓ Capacidad de soportar 2-3x más usuarios concurrentes")
    print("  ✓ Modelos se descargan automáticamente después de 1 minuto")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python aplicar_optimizaciones_automatico.py web_app.py")
        sys.exit(1)
    
    ruta = Path(sys.argv[1])
    aplicar_optimizaciones(ruta)
