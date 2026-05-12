# Test script para verificar imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from orchestrator import (
        call_ollama,
        pipeline_codigo,
        pipeline_vision,
        extract_code_blocks,
        save_code_blocks,
        start_ollama,
        PROMPT_ARQUITECTO
    )
    print("✅ Imports correctos")
except ImportError as e:
    print(f"❌ Error de import: {e}")
