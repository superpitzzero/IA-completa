from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs" / "comparativas"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _try_token_count(text: str) -> Tuple[int, str]:
    """
    Returns (token_count, method).
    - If `tiktoken` exists, use it (best-effort).
    - Otherwise fallback to a crude heuristic (words).
    """
    text = text or ""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken:cl100k_base"
    except Exception:
        # heuristic: "tokens" ~= words (very rough). We label it explicitly.
        words = [w for w in (text or "").strip().split() if w]
        return len(words), "heuristic:words"


@dataclass
class LocalCaseResult:
    case_id: str
    mode: str
    prompt_chars: int
    ok: bool
    error: str
    provider: str
    model: str
    ttft_ms: Optional[int]
    total_ms: int
    output_chars: int
    output_tokens: int
    token_count_method: str
    tokens_per_s: Optional[float]
    text_preview: str


def _stream_local_via_web_app(mode: str, prompt: str) -> LocalCaseResult:
    """
    Uses the project's internal stream generator (`web_app.stream_answer`)
    so we measure the same path used by the web UI.
    """
    import web_app  # local import (repo)

    chat = {"id": "comparativa_offline", "user_id": "comparativa_offline", "messages": []}
    settings = web_app.load_ai_settings()

    gen = web_app.stream_answer(
        chat,
        prompt,
        mode,
        attachments=[],
        ai_settings=settings,
    )

    provider = ""
    model = ""
    out_parts: List[str] = []
    ttft_ms: Optional[int] = None
    t0 = time.perf_counter()

    ok = True
    err = ""

    while True:
        try:
            raw = next(gen)
        except StopIteration as done:
            meta = done.value if isinstance(done.value, dict) else {}
            provider = provider or str(meta.get("provider") or "")
            model = model or str(meta.get("model") or "")
            break
        except Exception as exc:
            ok = False
            err = f"stream exception: {exc}"
            break

        try:
            event = json.loads(raw)
        except Exception:
            continue

        et = event.get("type")
        if et == "provider":
            provider = str(event.get("provider") or provider)
            model = str(event.get("model") or model)
        elif et == "error":
            ok = False
            err = str(event.get("message") or "error")
        elif et == "token":
            tok = str(event.get("token") or "")
            if tok:
                if ttft_ms is None:
                    ttft_ms = _ms(time.perf_counter() - t0)
                out_parts.append(tok)

    total_ms = _ms(time.perf_counter() - t0)
    text = "".join(out_parts).strip()
    token_count, method = _try_token_count(text)
    tps = None
    if total_ms > 0 and token_count > 0:
        tps = token_count / (total_ms / 1000.0)

    return LocalCaseResult(
        case_id="",
        mode=mode,
        prompt_chars=len(prompt),
        ok=ok,
        error=err,
        provider=provider or "local",
        model=model or (settings.get("openai_model") if provider == "openai" else ""),
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        output_chars=len(text),
        output_tokens=token_count,
        token_count_method=method,
        tokens_per_s=tps,
        text_preview=text[:240],
    )


def run_local_benchmark(prompts_path: Path, repeats: int) -> Dict[str, Any]:
    prompts = _load_json(prompts_path)
    cases = prompts.get("cases") if isinstance(prompts, dict) else None
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"Formato inválido en {prompts_path}")

    results: List[Dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "").strip() or "case"
        mode = str(case.get("mode") or "rapido").strip()
        prompt = str(case.get("prompt") or "").strip()
        if not prompt:
            continue

        for r in range(repeats):
            res = _stream_local_via_web_app(mode=mode, prompt=prompt)
            res.case_id = case_id
            results.append({**res.__dict__, "repeat": r + 1})

    return {
        "generated_at": _utc_now_iso(),
        "prompts_file": str(prompts_path),
        "repeats": repeats,
        "results": results,
    }


def _md_escape(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")


def render_markdown_report(
    *,
    model_cards: Dict[str, Any],
    local_results: Dict[str, Any],
    out_dir: Path,
    title: str,
) -> Tuple[Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"comparativa_offline_{ts}.md"
    html_path = out_dir / f"comparativa_offline_{ts}.html"

    models = model_cards.get("models") if isinstance(model_cards, dict) else []
    local = local_results.get("results") if isinstance(local_results, dict) else []

    md_lines: List[str] = []
    md_lines.append(f"## {title}")
    md_lines.append("")
    md_lines.append(f"- **Generado**: `{_utc_now_iso()}`")
    md_lines.append(f"- **Host**: `{os.getenv('COMPUTERNAME') or ''}`")
    md_lines.append("")

    md_lines.append("### Resultados locales (medidos en este equipo)")
    md_lines.append("")
    if not local:
        md_lines.append("_Sin resultados locales._")
    else:
        md_lines.append("| case | mode | ok | TTFT (ms) | total (ms) | out_tokens | tokens/s | token_count | provider | model | preview |")
        md_lines.append("|---|---:|:---:|---:|---:|---:|---:|---|---|---|---|")
        for row in local:
            ttft = row.get("ttft_ms")
            tps = row.get("tokens_per_s")
            md_lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("case_id") or ""),
                        str(row.get("mode") or ""),
                        "✅" if row.get("ok") else "❌",
                        "" if ttft is None else str(ttft),
                        str(row.get("total_ms") or ""),
                        str(row.get("output_tokens") or ""),
                        "" if tps is None else f"{float(tps):.2f}",
                        str(row.get("token_count_method") or ""),
                        str(row.get("provider") or ""),
                        str(row.get("model") or ""),
                        _md_escape(str(row.get("text_preview") or "")).replace("\n", " "),
                    ]
                )
                + " |"
            )
        md_lines.append("")
        md_lines.append("Notas:")
        md_lines.append("- `TTFT`: tiempo hasta el primer token (streaming).")
        md_lines.append("- `tokens/s`: depende de `token_count`. Si no hay `tiktoken`, se usa heurística y se marca.")

    md_lines.append("")
    md_lines.append("### Model cards externas (información pública)")
    md_lines.append("")
    if not isinstance(models, list) or not models:
        md_lines.append("_Sin model cards externas._")
    else:
        md_lines.append("| provider | model | release_date | context | max_output | pricing (in/out $/MTok) | benchmarks | sources |")
        md_lines.append("|---|---|---|---:|---:|---|---|---|")
        for m in models:
            if not isinstance(m, dict):
                continue
            pricing = m.get("pricing") if isinstance(m.get("pricing"), dict) else {}
            bench_list = m.get("benchmarks") if isinstance(m.get("benchmarks"), list) else []
            bench_names = ", ".join([str(b.get("name") or "") for b in bench_list if isinstance(b, dict) and b.get("name")])
            sources = m.get("sources") if isinstance(m.get("sources"), list) else []
            sources_txt = ", ".join([f"[link]({s})" for s in sources if isinstance(s, str) and s.startswith("http")])

            in_p = pricing.get("input_per_mtok_usd")
            out_p = pricing.get("output_per_mtok_usd")
            md_lines.append(
                "| "
                + " | ".join(
                    [
                        str(m.get("provider") or ""),
                        str(m.get("model") or ""),
                        str(m.get("release_date") or ""),
                        "" if m.get("context_window_tokens") is None else str(m.get("context_window_tokens")),
                        "" if m.get("max_output_tokens") is None else str(m.get("max_output_tokens")),
                        f"{'' if in_p is None else in_p}/{'' if out_p is None else out_p}",
                        bench_names,
                        sources_txt,
                    ]
                )
                + " |"
            )

    md = "\n".join(md_lines) + "\n"
    md_path.write_text(md, encoding="utf-8")

    html = (
        "<!doctype html><meta charset='utf-8' />"
        "<title>Comparativa offline</title>"
        "<style>body{font-family:system-ui,Segoe UI,Arial;margin:24px}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ddd;padding:6px;vertical-align:top}th{background:#f6f6f6}</style>"
        "<pre style='white-space:pre-wrap'></pre>"
        "<script>"
        "const md = " + json.dumps(md) + ";"
        "document.querySelector('pre').textContent = md;"
        "</script>"
    )
    html_path.write_text(html, encoding="utf-8")

    return md_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparativa offline (sin APIs): model cards públicos + rendimiento local")
    parser.add_argument("--model-cards", default=str(DATA_DIR / "model_cards.json"), help="Ruta a model_cards.json")
    parser.add_argument("--prompts", default=str(DATA_DIR / "prompts_local.json"), help="Ruta a prompts_local.json")
    parser.add_argument("--repeats", type=int, default=2, help="Repeticiones por caso (para estabilizar mediciones)")
    parser.add_argument("--out-dir", default=str(LOG_DIR), help="Directorio de salida (md/html/json)")
    parser.add_argument("--title", default="Comparativa offline (local vs externos)", help="Título del reporte")
    args = parser.parse_args()

    model_cards_path = Path(args.model_cards)
    prompts_path = Path(args.prompts)
    out_dir = Path(args.out_dir)
    _ensure_dir(out_dir)

    model_cards = _load_json(model_cards_path) if model_cards_path.exists() else {"models": []}
    local_results = run_local_benchmark(prompts_path=prompts_path, repeats=max(1, int(args.repeats)))

    md_path, html_path = render_markdown_report(
        model_cards=model_cards,
        local_results=local_results,
        out_dir=out_dir,
        title=str(args.title),
    )

    # Also dump raw JSON for future plotting/analysis
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = out_dir / f"comparativa_offline_{ts}.json"
    raw_path.write_text(
        json.dumps({"model_cards": model_cards, "local_results": local_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"OK. Reporte Markdown: {md_path}")
    print(f"OK. Reporte HTML: {html_path}")
    print(f"OK. Datos JSON: {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

