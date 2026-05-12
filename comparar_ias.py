from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent


def _now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    _safe_mkdir(path.parent)
    path.write_text(text, encoding="utf-8", errors="replace")


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


def estimate_tokens(text: str) -> int:
    # Heurística simple y consistente: ~4 chars/token (inglés), español similar.
    # No depende de librerías/SDKs.
    t = (text or "").strip()
    if not t:
        return 0
    return max(1, int(len(t) / 4))


def estimate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Tuple[Optional[float], str]:
    """
    Coste estimado: usa variables de entorno (por 1M tokens) si existen.
    - OPENAI_COST_PER_1M_INPUT, OPENAI_COST_PER_1M_OUTPUT
    - ANTHROPIC_COST_PER_1M_INPUT, ANTHROPIC_COST_PER_1M_OUTPUT
    - GEMINI_COST_PER_1M_INPUT, GEMINI_COST_PER_1M_OUTPUT
    """
    p = provider.lower().strip()
    prefix = {"openai": "OPENAI", "anthropic": "ANTHROPIC", "gemini": "GEMINI"}.get(p)
    if not prefix:
        return None, "n/a"

    in_price = _env(f"{prefix}_COST_PER_1M_INPUT")
    out_price = _env(f"{prefix}_COST_PER_1M_OUTPUT")
    if not in_price or not out_price:
        return None, "set *_COST_PER_1M_INPUT/OUTPUT env vars to estimate"
    try:
        pin = float(in_price)
        pout = float(out_price)
    except Exception:
        return None, "invalid *_COST_PER_1M_* values"

    cost = (input_tokens / 1_000_000.0) * pin + (output_tokens / 1_000_000.0) * pout
    return float(cost), f"estimated via {prefix}_COST_PER_1M_*"


@dataclass
class BenchPrompt:
    id: str
    category: str
    title: str
    prompt: str
    system: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass
class RunResult:
    provider: str
    model: str
    prompt_id: str
    category: str
    title: str
    latency_ms: int
    input_tokens_est: int
    output_tokens_est: int
    cost_usd_est: Optional[float]
    cost_note: str
    ok: bool
    error: str
    response_text: str


def load_bench_prompts(path: Path) -> Tuple[Dict[str, Any], List[BenchPrompt]]:
    if not path.exists():
        raise FileNotFoundError(f"No existe input: {path}")

    if path.suffix.lower() == ".json":
        data = json.loads(_read_text(path))
        defaults = data.get("defaults") if isinstance(data, dict) else {}
        prompts_raw = data.get("prompts") if isinstance(data, dict) else None
        if not isinstance(prompts_raw, list):
            raise ValueError("JSON inválido: se esperaba {prompts:[...]}.")

        out: List[BenchPrompt] = []
        for item in prompts_raw:
            if not isinstance(item, dict):
                continue
            out.append(
                BenchPrompt(
                    id=str(item.get("id") or "").strip(),
                    category=str(item.get("category") or "").strip() or "misc",
                    title=str(item.get("title") or "").strip() or str(item.get("id") or "prompt"),
                    prompt=str(item.get("prompt") or ""),
                    system=str(item.get("system") or ""),
                    temperature=(item.get("temperature") if item.get("temperature") is not None else defaults.get("temperature")),
                    max_tokens=(item.get("max_tokens") if item.get("max_tokens") is not None else defaults.get("max_tokens")),
                )
            )
        meta = {"format": "json", "defaults": defaults, "raw": data}
        return meta, [p for p in out if p.id and p.prompt.strip()]

    if path.suffix.lower() in {".csv", ".tsv"}:
        delim = "," if path.suffix.lower() == ".csv" else "\t"
        out2: List[BenchPrompt] = []
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                out2.append(
                    BenchPrompt(
                        id=str(row.get("id") or "").strip(),
                        category=str(row.get("category") or "").strip() or "misc",
                        title=str(row.get("title") or "").strip() or str(row.get("id") or "prompt"),
                        prompt=str(row.get("prompt") or ""),
                        system=str(row.get("system") or ""),
                        temperature=float(row["temperature"]) if (row.get("temperature") or "").strip() else None,
                        max_tokens=int(row["max_tokens"]) if (row.get("max_tokens") or "").strip() else None,
                    )
                )
        meta = {"format": "csv", "delimiter": delim, "raw": {"path": str(path)}}
        return meta, [p for p in out2 if p.id and p.prompt.strip()]

    raise ValueError("Formato no soportado. Usa .json o .csv/.tsv")


def detect_enabled_providers() -> Dict[str, bool]:
    enabled = {
        "local": True,
        "openai": bool(_env("OPENAI_API_KEY")),
        "anthropic": bool(_env("ANTHROPIC_API_KEY")),
        "gemini": bool(_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")),
    }
    return enabled


def _hash_prompt_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:10]


def call_local(prompt: BenchPrompt, model: str) -> str:
    """
    Local sin clave: preferimos la integración existente del repo.
    - Si `model` es 'arquitecto'/'programador'/'vision': usa `orchestrator.call_ollama(model_key=...)`
    - Si `model` parece un nombre de modelo Ollama (contiene ':' o letras/números): llama directo a `OLLAMA_HOST/api/chat`
    """
    try:
        import orchestrator as o  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"No se pudo importar orchestrator.py (IA local): {exc}") from exc

    model = (model or "").strip() or "programador"
    model_lower = model.lower()

    if model_lower in {"arquitecto", "programador", "vision"}:
        # Usamos el system prompt del bench si está definido.
        system = (prompt.system or "").strip()
        # No streaming para medir latencia completa de forma consistente.
        return str(o.call_ollama(model_lower, prompt.prompt, system=system, images=None, stream=False) or "").strip()

    # Fallback: llamada directa a Ollama con el nombre de modelo.
    try:
        import requests  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Falta dependencia 'requests' para local Ollama: {exc}") from exc

    host = getattr(o, "OLLAMA_HOST", "http://localhost:11434")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": ([{"role": "system", "content": prompt.system}] if (prompt.system or "").strip() else [])
        + [{"role": "user", "content": prompt.prompt}],
        "stream": False,
        "keep_alive": _env("NEXO_OLLAMA_KEEP_ALIVE") or _env("IA_OLLAMA_KEEP_ALIVE") or "30m",
        "options": {
            "temperature": float(prompt.temperature) if prompt.temperature is not None else 0.2,
            "num_predict": int(prompt.max_tokens) if prompt.max_tokens is not None else 512,
        },
    }

    s = requests.Session()
    r = s.post(f"{host}/api/chat", json=payload, timeout=(10, 300))
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    return str((((data or {}).get("message") or {}).get("content") or "")).strip()


def call_openai(prompt: BenchPrompt, model: str) -> str:
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY no configurada.")
    chosen_model = (model or "").strip() or _env("OPENAI_MODEL") or "gpt-5.5"

    # Preferimos SDK si está instalado (ya está en requirements_web.txt).
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        OpenAI = None  # type: ignore

    if OpenAI is not None:
        client = OpenAI(api_key=key)
        messages: List[Dict[str, str]] = []
        if (prompt.system or "").strip():
            messages.append({"role": "system", "content": prompt.system})
        messages.append({"role": "user", "content": prompt.prompt})
        resp = client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            temperature=float(prompt.temperature) if prompt.temperature is not None else 0.2,
            max_tokens=int(prompt.max_tokens) if prompt.max_tokens is not None else 512,
        )
        return str((resp.choices[0].message.content or "")).strip()

    # Fallback sin SDK: placeholder (no rompemos el flujo del script).
    raise RuntimeError("SDK openai no instalado. Instala 'openai' o usa requirements_web.txt.")


def call_anthropic(prompt: BenchPrompt, model: str) -> str:
    key = _env("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada.")
    chosen_model = (model or "").strip() or _env("ANTHROPIC_MODEL") or "claude-3-7-sonnet-latest"
    url = "https://api.anthropic.com/v1/messages"

    try:
        import requests  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Falta dependencia 'requests' para Anthropic: {exc}") from exc

    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": int(prompt.max_tokens) if prompt.max_tokens is not None else 512,
        "temperature": float(prompt.temperature) if prompt.temperature is not None else 0.2,
        "messages": [{"role": "user", "content": prompt.prompt}],
    }
    if (prompt.system or "").strip():
        payload["system"] = prompt.system

    r = requests.post(url, headers=headers, json=payload, timeout=(20, 300))
    if r.status_code >= 400:
        raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    content = data.get("content") or []
    if isinstance(content, list) and content:
        # Anthropic: content=[{type:"text",text:"..."}]
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "".join(parts).strip()
    return ""


def call_gemini(prompt: BenchPrompt, model: str) -> str:
    key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY o GOOGLE_API_KEY no configurada.")
    chosen_model = (model or "").strip() or _env("GEMINI_MODEL") or "gemini-1.5-pro"
    # Google Generative Language API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{chosen_model}:generateContent?key={key}"

    try:
        import requests  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Falta dependencia 'requests' para Gemini: {exc}") from exc

    # Gemini usa contents/parts
    parts: List[Dict[str, str]] = []
    if (prompt.system or "").strip():
        # No hay "system" como tal en este endpoint clásico; lo inyectamos como prefijo.
        parts.append({"text": f"[SYSTEM]\n{prompt.system}\n\n"})
    parts.append({"text": prompt.prompt})
    payload: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": float(prompt.temperature) if prompt.temperature is not None else 0.2,
            "maxOutputTokens": int(prompt.max_tokens) if prompt.max_tokens is not None else 512,
        },
    }

    r = requests.post(url, json=payload, timeout=(20, 300))
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    candidates = data.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return ""
    c0 = candidates[0] or {}
    content = c0.get("content") or {}
    cparts = content.get("parts") or []
    out_text = []
    for p in cparts:
        if isinstance(p, dict) and "text" in p:
            out_text.append(str(p.get("text") or ""))
    return "".join(out_text).strip()


def run_one(provider: str, model: str, bp: BenchPrompt) -> RunResult:
    p = provider.lower().strip()
    m = (model or "").strip()

    t0 = time.perf_counter()
    ok = True
    err = ""
    text = ""
    try:
        if p == "local":
            text = call_local(bp, m)
            used_model = m or "programador"
        elif p == "openai":
            text = call_openai(bp, m)
            used_model = m or _env("OPENAI_MODEL") or "gpt-5.5"
        elif p == "anthropic":
            text = call_anthropic(bp, m)
            used_model = m or _env("ANTHROPIC_MODEL") or "claude-3-7-sonnet-latest"
        elif p == "gemini":
            text = call_gemini(bp, m)
            used_model = m or _env("GEMINI_MODEL") or "gemini-1.5-pro"
        else:
            raise RuntimeError(f"Provider no soportado: {provider}")
    except Exception as exc:
        ok = False
        err = str(exc)
        text = ""
        used_model = m or "(default)"

    latency = _ms(time.perf_counter() - t0)
    input_tokens = estimate_tokens((bp.system or "") + "\n" + (bp.prompt or ""))
    output_tokens = estimate_tokens(text)
    cost, cost_note = estimate_cost_usd(p, used_model, input_tokens, output_tokens)

    return RunResult(
        provider=p,
        model=used_model,
        prompt_id=bp.id or _hash_prompt_id(bp.prompt),
        category=bp.category,
        title=bp.title,
        latency_ms=latency,
        input_tokens_est=input_tokens,
        output_tokens_est=output_tokens,
        cost_usd_est=cost,
        cost_note=cost_note,
        ok=ok,
        error=err,
        response_text=text,
    )


def render_markdown_report(
    meta: Dict[str, Any],
    prompts: List[BenchPrompt],
    results: List[RunResult],
    providers: List[Tuple[str, str]],
    out_base: Path,
) -> str:
    enabled = detect_enabled_providers()
    ts = _now_stamp()
    lines: List[str] = []
    lines.append(f"# Comparativa de IAs — {ts}")
    lines.append("")
    lines.append("## Configuración")
    lines.append("")
    lines.append(f"- **input**: `{str(meta.get('raw', {}).get('path') or meta.get('raw', {}).get('input') or '')}`".rstrip())
    lines.append(f"- **prompts**: {len(prompts)}")
    lines.append(f"- **providers solicitados**: {', '.join([f'{p}:{m or '(default)'}' for p, m in providers])}")
    lines.append(f"- **providers habilitados por env**: {', '.join([k for k, v in enabled.items() if v])}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    # resumen por provider
    by_provider: Dict[str, List[RunResult]] = {}
    for r in results:
        by_provider.setdefault(r.provider, []).append(r)
    for prov, items in by_provider.items():
        ok_count = sum(1 for x in items if x.ok)
        avg_ms = int(sum(x.latency_ms for x in items) / max(1, len(items)))
        lines.append(f"- **{prov}**: OK {ok_count}/{len(items)} · latencia media {avg_ms} ms")
    lines.append("")
    lines.append("## Detalle (por prompt)")
    lines.append("")

    # Orden estable: prompts y providers
    provider_order = [p for p, _ in providers]
    provider_model = {p: m for p, m in providers}
    result_map: Dict[Tuple[str, str], RunResult] = {(r.prompt_id, r.provider): r for r in results}

    for bp in prompts:
        lines.append(f"### {bp.id} — {bp.title}")
        lines.append("")
        lines.append(f"- **category**: `{bp.category}`")
        lines.append(f"- **prompt**:")
        lines.append("")
        lines.append("```")
        lines.append((bp.prompt or "").rstrip())
        lines.append("```")
        lines.append("")

        for prov in provider_order:
            r = result_map.get((bp.id, prov))
            if not r:
                continue
            cost_str = f"${r.cost_usd_est:.6f}" if isinstance(r.cost_usd_est, float) else "n/a"
            status = "OK" if r.ok else "ERROR"
            lines.append(f"#### {prov} ({r.model}) — {status}")
            lines.append("")
            lines.append(f"- **latency_ms**: {r.latency_ms}")
            lines.append(f"- **tokens_est**: in={r.input_tokens_est} · out={r.output_tokens_est}")
            lines.append(f"- **cost_est**: {cost_str} ({r.cost_note})")
            if not r.ok:
                lines.append(f"- **error**: `{r.error}`")
                lines.append("")
                continue
            lines.append("")
            lines.append("```")
            lines.append((r.response_text or "").rstrip())
            lines.append("```")
            lines.append("")

    # hints
    lines.append("## Notas")
    lines.append("")
    lines.append("- **Tokens/coste**: estimados con heurística simple. Para coste real, configura `*_COST_PER_1M_INPUT/OUTPUT`.")
    lines.append("- **Sin claves**: si no hay `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` (`GOOGLE_API_KEY`), el script corre solo `local` y deja el resto como no disponible.")
    lines.append("")
    lines.append(f"- **Artefactos**: reporte y JSON en `{out_base.as_posix()}`")
    return "\n".join(lines) + "\n"


def render_html_from_markdown(md_text: str) -> str:
    # HTML simple (sin dependencias): escapamos y renderizamos headings/code básicos.
    import html

    escaped = html.escape(md_text)
    # Muy básico: convertir ``` blocks a <pre>
    out: List[str] = []
    in_code = False
    for line in escaped.splitlines():
        if line.strip() == "```":
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        # headings
        if line.startswith("# "):
            out.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("#### "):
            out.append(f"<h4>{line[5:]}</h4>")
        elif line.startswith("- "):
            out.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            out.append("<br/>")
        else:
            out.append(f"<p>{line}</p>")

    body = "\n".join(out)
    return (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<title>Comparativa IAs</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px}"
        "pre{background:#0b0f14;color:#e6edf3;padding:12px;border-radius:8px;overflow:auto}"
        "code{background:#f2f2f2;padding:2px 4px;border-radius:4px}"
        "h1,h2,h3{margin-top:22px}li{margin-left:18px}</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def parse_provider_models(args_provider: str, args_model: str) -> List[Tuple[str, str]]:
    # --provider puede ser: local | openai | anthropic | gemini | auto | all | "local,openai"
    prov_raw = (args_provider or "").strip().lower() or "auto"
    model_raw = (args_model or "").strip()

    enabled = detect_enabled_providers()

    if prov_raw in {"auto"}:
        wanted = ["local"]
        for p in ("openai", "anthropic", "gemini"):
            if enabled.get(p):
                wanted.append(p)
        # si no hay claves, solo local
        return [(p, model_raw if p == "local" else "") for p in wanted]

    if prov_raw in {"all"}:
        wanted2 = ["local", "openai", "anthropic", "gemini"]
        # si no están habilitados, igualmente se intentan y fallan con error claro
        return [(p, model_raw if p == "local" else "") for p in wanted2]

    parts = [p.strip() for p in prov_raw.split(",") if p.strip()]
    if not parts:
        parts = ["auto"]
    return [(p, model_raw if p == "local" else "") for p in parts]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Comparar IA local (Nexo/Ollama) con OpenAI/Claude/Gemini (si hay claves).")
    parser.add_argument("--provider", default="auto", help="auto|local|openai|anthropic|gemini|all o lista separada por coma")
    parser.add_argument("--model", default="", help="Modelo. Para local: 'programador'/'arquitecto' o nombre Ollama (ej qwen2.5-coder:7b).")
    parser.add_argument("--input", default=str(ROOT / "prompts" / "bench.json"), help="Ruta a bench.json o .csv/.tsv")
    parser.add_argument("--out", default="", help="Ruta de salida (.md). Por defecto logs/comparativas/")
    parser.add_argument("--html", action="store_true", help="Genera también .html")
    parser.add_argument("--only-category", default="", help="Filtra por categoría (chat|code|reasoning|tool|...)")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    meta, prompts = load_bench_prompts(input_path)
    meta["raw"] = {"input": str(input_path)}

    if args.only_category:
        cat = args.only_category.strip().lower()
        prompts = [p for p in prompts if (p.category or "").strip().lower() == cat]

    if not prompts:
        print("No hay prompts para ejecutar (¿filtro incorrecto?).")
        return 2

    providers = parse_provider_models(args.provider, args.model)

    out_dir = ROOT / "logs" / "comparativas"
    _safe_mkdir(out_dir)

    out_md = Path(args.out).expanduser() if args.out else (out_dir / f"comparativa_{_now_stamp()}.md")
    if out_md.suffix.lower() != ".md":
        out_md = out_md.with_suffix(".md")
    out_json = out_md.with_suffix(".json")
    out_html = out_md.with_suffix(".html")

    results: List[RunResult] = []
    for prov, model in providers:
        for bp in prompts:
            print(f"[{prov}] {bp.id}...", flush=True)
            r = run_one(prov, model, bp)
            results.append(r)

    # persist JSON (útil para análisis posterior)
    json_payload: Dict[str, Any] = {
        "ts": _now_stamp(),
        "input": str(input_path),
        "providers": [{"provider": p, "model": m} for p, m in providers],
        "prompts": [p.__dict__ for p in prompts],
        "results": [r.__dict__ for r in results],
        "env_enabled": detect_enabled_providers(),
    }
    _write_text(out_json, json.dumps(json_payload, ensure_ascii=False, indent=2))

    md = render_markdown_report(meta, prompts, results, providers, out_dir)
    _write_text(out_md, md)

    if args.html:
        _write_text(out_html, render_html_from_markdown(md))

    print(f"\nReporte: {out_md}")
    print(f"JSON:    {out_json}")
    if args.html:
        print(f"HTML:    {out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

