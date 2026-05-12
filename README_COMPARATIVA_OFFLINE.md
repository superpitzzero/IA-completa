## Comparativa offline (sin APIs)

Este módulo genera una **comparativa offline** combinando:

- **Model cards externas** con datos públicos (contexto, pricing, links de benchmarks).
- **Métricas reales locales** contra tu IA en este equipo: **TTFT** (time-to-first-token) y **tokens/s**.

Importante: **no se inventan números**. Si un campo no tiene fuente pública fiable, queda vacío (`null` / vacío) y se mantiene el link.

### Archivos

- `data/model_cards.json`: model cards externos con fuentes públicas.
- `data/prompts_local.json`: prompts repetibles para medir localmente.
- `comparativa_offline.py`: ejecuta la medición local y genera reporte.
- `COMPARAR_OFFLINE.bat`: wrapper para Windows que deja outputs en `logs\comparativas`.

### Cómo ejecutar (Windows)

Desde la raíz del repo:

```bash
COMPARAR_OFFLINE.bat
```

Opcionales:

```bash
COMPARAR_OFFLINE.bat --repeats 3
COMPARAR_OFFLINE.bat --title "Comparativa mayo 2026"
```

### Salidas

Se generan 3 archivos por corrida en `logs\comparativas`:

- `comparativa_offline_YYYYMMDD_HHMMSS.md`
- `comparativa_offline_YYYYMMDD_HHMMSS.html` (viewer simple, sin conversión Markdown)
- `comparativa_offline_YYYYMMDD_HHMMSS.json` (raw, para análisis posterior)

### Fuentes públicas incluidas (ejemplos)

- Claude context windows: `https://platform.claude.com/docs/en/build-with-claude/context-windows`
- OpenAI models (pricing/context): `https://developers.openai.com/api/docs/models`
- Gemini 2.5 Pro (Vertex): `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro`
- Gemini long context: `https://ai.google.dev/gemini-api/docs/long-context`
- SWE-bench leaderboard: `https://www.swebench.com/`
- Arena: `https://lmarena.ai/`

