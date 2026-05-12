"""
Ejemplos de uso avanzado del Orchestrator

Demuestra cómo usar el orquestador como librería en tus propios scripts
"""

# Importar el orquestador
import sys
from pathlib import Path

# Asegurar que está en el path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import (
    call_ollama,
    pipeline_codigo,
    pipeline_vision,
    extract_code_blocks,
    save_code_blocks,
    start_ollama,
    PROMPT_ARQUITECTO,
    ask,
)

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 1: Generar múltiples archivos de un proyecto
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_proyecto_completo():
    """Genera múltiples archivos para un proyecto"""
    print("📦 Generando proyecto Flask...")
    
    # Asegurar que Ollama está corriendo
    start_ollama()
    
    archivos_a_generar = [
        ("app.py", "Aplicación Flask básica con ruta /api/users"),
        ("models.py", "Modelo SQLAlchemy para Usuario con email y password"),
        ("requirements.txt", "Dependencias para Flask, SQLAlchemy, Flask-JWT"),
    ]
    
    for filename, descripcion in archivos_a_generar:
        print(f"\n🔨 Generando {filename}...")
        resultado = call_ollama(
            "programador",
            f"Crea {descripcion}. Solo el código, sin explicaciones.",
            stream=False
        )
        
        # Extraer código
        blocks = extract_code_blocks(resultado)
        if blocks:
            Path(f"proyecto_flask/{filename}").parent.mkdir(exist_ok=True)
            Path(f"proyecto_flask/{filename}").write_text(blocks[0]["code"])
            print(f"✅ {filename} creado")

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 2: Code review automatizado
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_code_review(archivo_codigo: str):
    """Realiza code review de un archivo"""
    print(f"🔍 Analizando {archivo_codigo}...")
    
    # Leer código
    codigo = Path(archivo_codigo).read_text()
    
    # Review con arquitecto
    prompt = f"""Realiza un code review profesional de este código.
Identifica:
- Bugs y errores lógicos
- Problemas de seguridad
- Oportunidades de optimización
- Violaciones de best practices

Código:
```
{codigo}
```

Proporciona feedback constructivo y código corregido."""
    
    review = call_ollama("arquitecto", prompt, system=PROMPT_ARQUITECTO)
    
    # Guardar review
    review_path = Path(archivo_codigo).with_suffix(".review.md")
    review_path.write_text(review)
    print(f"✅ Review guardado en {review_path}")

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 3: Análisis batch de imágenes
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_analisis_imagenes(carpeta: str):
    """Analiza todas las imágenes en una carpeta"""
    print(f"👁️  Analizando imágenes en {carpeta}...")
    
    imagenes = list(Path(carpeta).glob("*.png")) + list(Path(carpeta).glob("*.jpg"))
    
    resultados = []
    for img in imagenes:
        print(f"\n📸 Procesando {img.name}...")
        resultado = pipeline_vision("Describe técnicamente esta imagen", str(img))
        resultados.append({
            "imagen": img.name,
            "analisis": resultado
        })
    
    # Guardar informe
    informe = "\n\n".join(
        f"## {r['imagen']}\n{r['analisis']}" 
        for r in resultados
    )
    Path("informe_imagenes.md").write_text(informe)
    print("✅ Informe guardado en informe_imagenes.md")

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 4: Generador de tests
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_generar_tests(archivo_codigo: str):
    """Genera tests unitarios para un archivo"""
    print(f"🧪 Generando tests para {archivo_codigo}...")
    
    codigo = Path(archivo_codigo).read_text()
    
    prompt = f"""Genera tests unitarios completos usando pytest para este código:

```python
{codigo}
```

Incluye:
- Tests de casos normales
- Tests de edge cases
- Tests de errores/excepciones
- Fixtures si son necesarios

Solo el código de tests, completo y funcional."""
    
    tests = call_ollama("programador", prompt)
    
    # Guardar tests
    test_file = Path(archivo_codigo).parent / f"test_{Path(archivo_codigo).name}"
    blocks = extract_code_blocks(tests)
    if blocks:
        test_file.write_text(blocks[0]["code"])
        print(f"✅ Tests guardados en {test_file}")

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 5: Refactorización inteligente
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_refactorizar(archivo_codigo: str):
    """Refactoriza código aplicando mejores prácticas"""
    print(f"♻️  Refactorizando {archivo_codigo}...")
    
    codigo = Path(archivo_codigo).read_text()
    
    prompt = f"""Refactoriza este código siguiendo SOLID, DRY, y clean code:

```python
{codigo}
```

Mejoras a aplicar:
- Extraer funciones/clases reutilizables
- Mejorar nombres de variables
- Añadir type hints
- Documentar con docstrings
- Optimizar algoritmos

Proporciona el código refactorizado completo."""
    
    refactorizado = pipeline_codigo(prompt)
    
    # Guardar versión refactorizada
    nuevo_archivo = Path(archivo_codigo).with_stem(f"{Path(archivo_codigo).stem}_refactored")
    blocks = extract_code_blocks(refactorizado)
    if blocks:
        nuevo_archivo.write_text(blocks[0]["code"])
        print(f"✅ Código refactorizado guardado en {nuevo_archivo}")

# ═══════════════════════════════════════════════════════════════════════
#  EJEMPLO 6: Documentación automática
# ═══════════════════════════════════════════════════════════════════════

def ejemplo_documentar(archivo_codigo: str):
    """Genera documentación para código"""
    print(f"📚 Documentando {archivo_codigo}...")
    
    codigo = Path(archivo_codigo).read_text()
    
    prompt = f"""Genera documentación completa para este código:

```python
{codigo}
```

Incluye:
- Descripción general del módulo
- Docstrings para todas las funciones/clases
- Ejemplos de uso
- Descripción de parámetros y retornos
- Notas sobre edge cases

Formato: Markdown con ejemplos de código."""
    
    docs = call_ollama("arquitecto", prompt, stream=False)
    
    # Guardar documentación
    doc_file = Path(archivo_codigo).with_suffix(".md")
    doc_file.write_text(docs)
    print(f"✅ Documentación guardada en {doc_file}")

# ═══════════════════════════════════════════════════════════════════════
#  MENÚ DE EJEMPLOS
# ═══════════════════════════════════════════════════════════════════════

def menu_ejemplos():
    """Menú interactivo de ejemplos"""
    ejemplos = {
        "1": ("📦 Generar proyecto completo", ejemplo_proyecto_completo),
        "2": ("🔍 Code review de archivo", 
              lambda: ejemplo_code_review(ask("Archivo: "))),
        "3": ("👁️  Análisis batch de imágenes", 
              lambda: ejemplo_analisis_imagenes(ask("Carpeta: "))),
        "4": ("🧪 Generar tests unitarios", 
              lambda: ejemplo_generar_tests(ask("Archivo: "))),
        "5": ("♻️  Refactorizar código", 
              lambda: ejemplo_refactorizar(ask("Archivo: "))),
        "6": ("📚 Generar documentación", 
              lambda: ejemplo_documentar(ask("Archivo: "))),
    }
    
    print("\n" + "="*70)
    print("🎯 EJEMPLOS AVANZADOS - Ollama Orchestrator")
    print("="*70)
    
    for key, (desc, _) in ejemplos.items():
        print(f"  {key}. {desc}")
    print("  0. Salir")
    
    while True:
        choice = ask("\nElige ejemplo: ", default="0").strip()
        
        if choice == "0":
            break
        
        if choice in ejemplos:
            print()
            try:
                ejemplos[choice][1]()
                print("\n✅ Ejemplo completado")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Opción no válida")

if __name__ == "__main__":
    # Asegurar Ollama corriendo
    start_ollama()
    
    # Mostrar menú
    menu_ejemplos()
