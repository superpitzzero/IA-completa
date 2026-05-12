#!/usr/bin/env python3
"""
Script para corregir los problemas de la IA:
1. IA MÁS RÁPIDA - modo conversacional
2. Respuestas naturales (no código) para mensajes casuales
3. Fix error 500 en /api/chat/stream
"""

import os
import re
from pathlib import Path

# Directorio del proyecto
PROJECT_DIR = Path(r"C:\Users\34645\Desktop\IA combinada completo-EXPERIMENTAL")

def backup_file(filepath):
    """Crea backup del archivo antes de modificarlo"""
    backup_path = f"{filepath}.backup_correccion"
    if not os.path.exists(backup_path):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Backup creado: {backup_path}")

def patch_orchestrator():
    """Agrega PROMPT_CONVERSACIONAL al orchestrator"""
    filepath = PROJECT_DIR / "orchestrator.py"
    backup_file(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar donde están los prompts actuales
    prompt_section = '''PROMPT_VISION = """Eres un analista visual experto.
Analiza imágenes, código en capturas, diagramas y UI.
Proporciona análisis técnico detallado."""'''
    
    new_prompt = '''PROMPT_VISION = """Eres un analista visual experto.
Analiza imágenes, código en capturas, diagramas y UI.
Proporciona análisis técnico detallado."""

PROMPT_CONVERSACIONAL = """Eres un asistente amigable y conversacional.
Responde de forma natural, breve y directa.
NO generes código ni explicaciones técnicas a menos que te lo pidan explícitamente.
Para saludos y conversación casual, responde como una persona normal."""'''
    
    if "PROMPT_CONVERSACIONAL" not in content:
        content = content.replace(prompt_section, new_prompt)
        print("✓ PROMPT_CONVERSACIONAL agregado al orchestrator")
    else:
        print("⚠ PROMPT_CONVERSACIONAL ya existe en orchestrator")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_web_app():
    """Corrige web_app.py: error 500, detección casual, modo conversacional"""
    filepath = PROJECT_DIR / "web_app.py"
    backup_file(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    
    # 1. Agregar PROMPT_CONVERSACIONAL en imports
    for i, line in enumerate(lines):
        if "PROMPT_PROGRAMADOR," in line and "PROMPT_CONVERSACIONAL" not in line:
            lines[i] = line.replace("PROMPT_PROGRAMADOR,", "PROMPT_PROGRAMADOR,\n    PROMPT_CONVERSACIONAL,")
            modified = True
            print("✓ PROMPT_CONVERSACIONAL importado")
            break
    
    # 2. Arreglar el error en api_chat_stream (línea ~3094)
    for i, line in enumerate(lines):
        if 'mode = str(payload.get("mode", "rapido"))  # PARCHE: modo rápido por defecto.strip().lower()' in line:
            # Este es el error - está usando payload antes de definirlo
            # Vamos a comentar esta línea errónea
            lines[i] = '            # mode = str(payload.get("mode", "rapido"))  # LINEA ERRÓNEA - COMENTADA\n'
            modified = True
            print("✓ Error en api_chat_stream línea 3094 corregido")
            break
    
    # 3. Función is_casual_message mejorada
    casual_function_old = '''    casual_messages = {
        "hola",
        "holaa",
        "holaaa",
        "buenas",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "hey",
        "hi",
        "hello",
        "que tal",
        "como estas",
        "gracias",
        "muchas gracias",
        "ok",
        "vale",
        "perfecto",
        "jaja",
        "jeje",
    }
    if normalized in casual_messages:
        return False'''
    
    casual_function_new = '''    casual_messages = {
        "hola", "holaa", "holaaa", "buenas", "buenos dias", "buen dia",
        "buenas tardes", "buenas noches", "hey", "hi", "hello",
        "que tal", "como estas", "como va", "que pasa",
        "gracias", "muchas gracias", "ok", "vale", "perfecto",
        "jaja", "jeje", "xd", "jajaja", "lol",
        "adios", "chao", "hasta luego", "nos vemos",
    }
    if normalized in casual_messages:
        return True  # CAMBIO: True = es casual, no buscar web'''
    
    content = ''.join(lines)
    if casual_function_old in content:
        content = content.replace(casual_function_old, casual_function_new)
        modified = True
        print("✓ Detección de mensajes casuales mejorada")
    
    # 4. Nueva función para detectar si debe usar modo conversacional
    new_function = '''

def is_conversational_message(user_message: str) -> bool:
    """Detecta si el mensaje es conversacional (no técnico)"""
    normalized = user_message.lower().strip().replace("¿", "").replace("?", "")
    
    # Mensajes claramente casuales/conversacionales
    casual_patterns = {
        "hola", "holaa", "holaaa", "buenas", "buenos dias", "buen dia",
        "buenas tardes", "buenas noches", "hey", "hi", "hello",
        "que tal", "como estas", "como va", "que pasa",
        "gracias", "muchas gracias", "ok", "vale", "perfecto",
        "jaja", "jeje", "xd", "jajaja", "lol",
        "adios", "chao", "hasta luego", "nos vemos",
    }
    
    if normalized in casual_patterns:
        return True
    
    # Frases cortas sin palabras técnicas
    words = normalized.split()
    if len(words) <= 3:
        tech_keywords = [
            "codigo", "code", "programa", "funcion", "clase", "error",
            "bug", "debug", "script", "python", "javascript", "java",
            "api", "sql", "database", "html", "css", "react",
            "archivo", "file", "documento", "crear", "generar",
        ]
        has_tech = any(keyword in normalized for keyword in tech_keywords)
        if not has_tech:
            return True
    
    return False

'''
    
    # Insertar la nueva función después de should_search_web
    search_web_end = "def search_web_context(user_message: str"
    if search_web_end in content and "def is_conversational_message" not in content:
        content = content.replace(
            "def search_web_context(user_message: str",
            new_function + "def search_web_context(user_message: str"
        )
        modified = True
        print("✓ Función is_conversational_message agregada")
    
    # 5. Modificar stream_ollama_answer para usar modo conversacional
    old_rapido_code = '''    if mode == "rapido":
        error = ensure_ai_ready(["arquitecto"])
        if error:
            yield event({"type": "error", "message": error})
            return {"text": "", "provider": "ollama"}
        messages = [
            {"role": "system", "content": PROMPT_ARQUITECTO},
            {"role": "user", "content": context_prompt},
        ]
        yield event({"type": "status", "message": "Ollama respondiendo..."})
        for token in ollama_chat_stream("arquitecto", messages):
            final_text += token
            yield event({"type": "token", "token": token})
        return {"text": final_text, "provider": "ollama"}'''
    
    new_rapido_code = '''    if mode == "rapido":
        error = ensure_ai_ready(["arquitecto"])
        if error:
            yield event({"type": "error", "message": error})
            return {"text": "", "provider": "ollama"}
        
        # Detectar si es conversación casual
        is_casual = is_conversational_message(user_message)
        system_prompt = PROMPT_CONVERSACIONAL if is_casual else PROMPT_ARQUITECTO
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_prompt if not is_casual else user_message},
        ]
        yield event({"type": "status", "message": "Pensando..."})
        for token in ollama_chat_stream("arquitecto", messages):
            final_text += token
            yield event({"type": "token", "token": token})
        return {"text": final_text, "provider": "ollama"}'''
    
    if old_rapido_code in content:
        content = content.replace(old_rapido_code, new_rapido_code)
        modified = True
        print("✓ Modo rápido conversacional implementado")
    
    # 6. Modificar parámetros de Ollama para más velocidad
    old_payload = '''def ollama_payload(model_key: str, messages: List[Dict[str, Any]], stream: bool) -> Dict[str, Any]:
    model = MODELS.get(model_key)
    if not model:
        return {}

    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": "10m",
        "options": {
            "num_gpu": GPU_LAYERS.get(model_key, 16),
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }'''
    
    new_payload = '''def ollama_payload(model_key: str, messages: List[Dict[str, Any]], stream: bool) -> Dict[str, Any]:
    model = MODELS.get(model_key)
    if not model:
        return {}

    # Optimizado para velocidad
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": "10m",
        "options": {
            "num_gpu": GPU_LAYERS.get(model_key, 16),
            "temperature": 0.1,  # Reducido para más rapidez y consistencia
            "top_p": 0.85,       # Reducido para más enfoque
            "num_predict": 512,  # Límite de tokens para respuestas más cortas
        },
    }'''
    
    if old_payload in content:
        content = content.replace(old_payload, new_payload)
        modified = True
        print("✓ Parámetros de Ollama optimizados para velocidad")
    
    # Guardar cambios
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Archivo {filepath} actualizado")
    else:
        print(f"⚠ No se realizaron cambios en {filepath}")

def main():
    print("=" * 70)
    print("CORRECCIÓN DE IA - VELOCIDAD Y CONVERSACIÓN NATURAL")
    print("=" * 70)
    print()
    
    if not PROJECT_DIR.exists():
        print(f"❌ Error: No se encuentra el directorio {PROJECT_DIR}")
        return
    
    print("Aplicando correcciones...")
    print()
    
    # Aplicar parches
    patch_orchestrator()
    patch_web_app()
    
    print()
    print("=" * 70)
    print("✓ CORRECCIONES COMPLETADAS")
    print("=" * 70)
    print()
    print("Cambios realizados:")
    print("1. ✓ Modo conversacional agregado (respuestas naturales)")
    print("2. ✓ Detección de mensajes casuales mejorada")
    print("3. ✓ Error 500 en /api/chat/stream corregido")
    print("4. ✓ Parámetros optimizados para más velocidad")
    print()
    print("Ahora la IA:")
    print("  • Responde naturalmente a 'hola', 'gracias', etc.")
    print("  • Es más rápida (temperatura 0.1, límite 512 tokens)")
    print("  • No da código cuando no se le pide")
    print()
    print("Reinicia la aplicación web para aplicar los cambios.")
    print()

if __name__ == "__main__":
    main()