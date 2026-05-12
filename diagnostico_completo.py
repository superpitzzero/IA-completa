from __future__ import annotations

import glob
import importlib
import json
import os
import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "diagnostico_completo.log"
PUBLIC_URL_RE = re.compile(
    r"https://[^\s|\"'<>]+(?:trycloudflare\.com|ngrok-free\.app|ngrok-free\.dev|ngrok-free\.pizza|ngrok\.app|ngrok\.dev|ngrok\.pizza|ngrok\.io)[^\s|\"'<>]*"
)
ANY_HTTPS_URL_RE = re.compile(r"https://[^\s|\"'<>]+")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _w(line: str = "") -> None:
    print(line, flush=True)
    LOG_FILE.open("a", encoding="utf-8", errors="replace").write(line + "\n")


def header(title: str) -> None:
    _w("")
    _w("=" * 78)
    _w(f"{title}  ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    _w("=" * 78)


def section(title: str) -> None:
    _w("")
    _w("-" * 78)
    _w(title)
    _w("-" * 78)


def check_py_compile() -> CheckResult:
    import py_compile

    files = sorted(glob.glob("**/*.py", recursive=True))
    bad: list[tuple[str, str]] = []
    for f in files:
        try:
            py_compile.compile(f, doraise=True)
        except Exception as exc:
            bad.append((f, str(exc)))

    detail = f"PY FILES={len(files)} BAD={len(bad)}"
    if bad:
        detail += "\n" + "\n".join([f"--- {f} ---\n{e}" for f, e in bad])
    return CheckResult("py_compile", ok=not bad, detail=detail)


def check_imports() -> CheckResult:
    sys.path.insert(0, str(ROOT))
    targets = ["orchestrator", "web_app", "launch_web"]
    errors: list[str] = []
    for name in targets:
        try:
            importlib.import_module(name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    ok = not errors
    detail = "OK" if ok else "\n".join(errors)
    return CheckResult("imports", ok=ok, detail=detail)


def check_openai_config() -> CheckResult:
    key_env = (os.getenv("OPENAI_API_KEY") or "").strip()
    settings_path = ROOT / "web_data" / "settings.json"
    key_file = ""
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                key_file = str(data.get("openai_api_key", "") or "").strip()
        except Exception:
            key_file = ""

    chosen = key_env or key_file
    provider = (os.getenv("AI_PROVIDER") or "").strip() or "auto"
    model = (os.getenv("OPENAI_MODEL") or "").strip() or "(default)"
    source = "env" if key_env else ("settings.json" if key_file else "none")

    # Never print the key itself.
    detail = (
        f"AI_PROVIDER={provider}\n"
        f"OPENAI_MODEL={model}\n"
        f"OPENAI_API_KEY configured={bool(chosen)}\n"
        f"OPENAI_API_KEY length={len(chosen)}\n"
        f"OPENAI_API_KEY source={source}"
    )
    return CheckResult("openai_config", ok=True, detail=detail)


def check_ollama_basic() -> CheckResult:
    try:
        import orchestrator as o
    except Exception as exc:
        return CheckResult("ollama", ok=False, detail=f"No se pudo importar orchestrator: {exc}")

    try:
        running = bool(o.is_ollama_running())
    except Exception as exc:
        return CheckResult("ollama", ok=False, detail=f"Fallo is_ollama_running(): {exc}")

    detail = f"OLLAMA_HOST={getattr(o,'OLLAMA_HOST', '')}\nOllama running={running}\nMODELS={getattr(o,'MODELS', {})}"
    return CheckResult("ollama", ok=running, detail=detail)


def _safe_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "s", "si", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalize_public_url(value: str) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return text.rstrip("/")


def settings_value(*names: str) -> str:
    settings_path = ROOT / "web_data" / "settings.json"
    if not settings_path.exists():
        return ""
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    for name in names:
        value = normalize_public_url(str(data.get(name) or ""))
        if value:
            return value
    return ""


def ngrok_url_file_value() -> str:
    path = ROOT / "web_data" / "ngrok_url.txt"
    if not path.exists():
        return ""
    try:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except Exception:
        return ""
    return normalize_public_url(first_line)


def latest_url_from_log(path: Path, pattern: re.Pattern[str]) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    matches = [normalize_public_url(match.group(0)) for match in pattern.finditer(text)]
    matches = [item for item in matches if item]
    return matches[-1] if matches else ""


def detect_public_url(cli_url: str = "") -> tuple[str, str]:
    candidates = [
        ("argumento", normalize_public_url(cli_url)),
        ("NEXO_PUBLIC_URL", normalize_public_url(_safe_env("NEXO_PUBLIC_URL"))),
        ("IA_PUBLIC_URL", normalize_public_url(_safe_env("IA_PUBLIC_URL"))),
        ("DIAG_PUBLIC_URL", normalize_public_url(_safe_env("DIAG_PUBLIC_URL"))),
        ("NEXO_NGROK_URL", normalize_public_url(_safe_env("NEXO_NGROK_URL") or _safe_env("NEXO_NGROK_DOMAIN"))),
        ("IA_NGROK_URL", normalize_public_url(_safe_env("IA_NGROK_URL") or _safe_env("IA_NGROK_DOMAIN"))),
        ("settings.json", settings_value("ngrok_url", "ngrok_domain", "public_url")),
        ("web_data/ngrok_url.txt", ngrok_url_file_value()),
        ("logs/ngrok.log", latest_url_from_log(LOG_DIR / "ngrok.log", PUBLIC_URL_RE)),
        ("logs/cloudflared.log", latest_url_from_log(LOG_DIR / "cloudflared.log", PUBLIC_URL_RE)),
        ("logs/ngrok.log https", latest_url_from_log(LOG_DIR / "ngrok.log", ANY_HTTPS_URL_RE)),
    ]
    for source, url in candidates:
        if url:
            return url, source
    return "", "none"


def fetch_status(url: str, timeout: float = 12.0) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Nexo-Diagnostico/1.0",
            "ngrok-skip-browser-warning": "1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(80_000)
        text = raw.decode("utf-8", errors="replace")
        final_url = getattr(response, "url", url)
        return int(response.status), str(final_url), text


def check_public_url(public_url: str = "") -> CheckResult:
    url, source = detect_public_url(public_url)
    if not url:
        return CheckResult(
            "public_url",
            ok=False,
            detail=(
                "No se encontro URL publica. Pasa una URL al .bat, configura NEXO_NGROK_URL "
                "o guarda el dominio fijo en web_data\\ngrok_url.txt."
            ),
        )

    login_url = url.rstrip("/") + "/login"
    t0 = time.perf_counter()
    try:
        status, final_url, body = fetch_status(login_url)
    except Exception as exc:
        return CheckResult("public_url", ok=False, detail=f"url={url}\nsource={source}\n/login fallo: {exc}")
    elapsed = _ms(time.perf_counter() - t0)

    body_ok = "Nexo" in body or "login" in body.lower() or "contrase" in body.lower()
    ok = 200 <= status < 400 and body_ok
    detail = (
        f"url={url}\n"
        f"source={source}\n"
        f"login_url={login_url}\n"
        f"status={status}\n"
        f"final_url={final_url}\n"
        f"latency_ms={elapsed}\n"
        f"body_check={body_ok}"
    )
    return CheckResult("public_url", ok=ok, detail=detail)


def collect_stream_answer(mode: str, prompt: str) -> tuple[str, list[str], dict[str, Any], int]:
    import web_app

    chat = {"id": "diagnostico", "user_id": "diagnostico", "messages": []}
    stream = web_app.stream_answer(
        chat,
        prompt,
        mode,
        attachments=[],
        ai_settings=web_app.load_ai_settings(),
    )
    text_parts: list[str] = []
    errors: list[str] = []
    final_meta: dict[str, Any] = {}
    t0 = time.perf_counter()
    while True:
        try:
            raw = next(stream)
        except StopIteration as done:
            if isinstance(done.value, dict):
                final_meta = done.value
            break
        try:
            event = json.loads(raw)
        except Exception:
            continue
        if event.get("type") == "token":
            text_parts.append(str(event.get("token") or ""))
        elif event.get("type") == "error":
            errors.append(str(event.get("message") or "error desconocido"))
    return "".join(text_parts).strip(), errors, final_meta, _ms(time.perf_counter() - t0)


def check_web_mode_responses() -> CheckResult:
    if parse_bool(_safe_env("NEXO_DIAG_SKIP_MODE_RESPONSES") or _safe_env("IA_DIAG_SKIP_MODE_RESPONSES"), default=False):
        return CheckResult("web_mode_responses", ok=True, detail="Saltado por NEXO_DIAG_SKIP_MODE_RESPONSES=1")

    prompts = {
        "rapido": "Responde solo: OK rapido",
        "combinado": "Responde en una frase que es una variable en programacion.",
        "codigo": "Genera codigo Python minimo que imprima OK.",
    }
    details: list[str] = []
    failures: list[str] = []
    banned = ("claude", "anthropic", "[nombre del usuario]")

    for mode, prompt in prompts.items():
        try:
            text, errors, meta, elapsed = collect_stream_answer(mode, prompt)
        except Exception as exc:
            failures.append(f"{mode}: excepcion {exc}")
            details.append(f"--- {mode} ---\nEXCEPCION={exc}")
            continue

        lower = text.lower()
        mode_failures = []
        if errors:
            mode_failures.append("errores=" + "; ".join(errors))
        if not text:
            mode_failures.append("respuesta vacia")
        if any(word in lower for word in banned):
            mode_failures.append("menciona identidad prohibida")
        if mode == "codigo" and "print" not in lower and "```" not in text:
            mode_failures.append("modo codigo no parece devolver codigo Python")

        if mode_failures:
            failures.append(f"{mode}: " + "; ".join(mode_failures))

        details.append(
            f"--- {mode} ---\n"
            f"ok={not mode_failures}\n"
            f"elapsed_ms={elapsed}\n"
            f"provider={meta.get('provider', '')}\n"
            f"reply_preview={text[:400]!r}"
        )

    return CheckResult("web_mode_responses", ok=not failures, detail="\n".join(details + failures))


def check_ollama_latency() -> CheckResult:
    """Mide latencia de una respuesta corta (stream=False) y del primer token (stream=True)."""
    try:
        import requests
    except Exception as exc:
        return CheckResult("ollama_latency", ok=False, detail=f"Falta requests: {exc}")

    try:
        import orchestrator as o
    except Exception as exc:
        return CheckResult("ollama_latency", ok=False, detail=f"No se pudo importar orchestrator: {exc}")

    host = getattr(o, "OLLAMA_HOST", "http://localhost:11434")
    model = None
    try:
        model = (getattr(o, "MODELS", {}) or {}).get("programador") or (getattr(o, "MODELS", {}) or {}).get("arquitecto")
    except Exception:
        model = None

    if not model:
        return CheckResult("ollama_latency", ok=False, detail="No hay modelo configurado en MODELS.")

    s = requests.Session()
    base_payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "Di solo: OK"}],
        "options": {"num_predict": 16, "temperature": 0.0},
        "keep_alive": _safe_env("NEXO_OLLAMA_KEEP_ALIVE") or _safe_env("IA_OLLAMA_KEEP_ALIVE") or "30m",
    }

    # 1) Non-stream latency
    t0 = time.perf_counter()
    try:
        r = s.post(f"{host}/api/chat", json={**base_payload, "stream": False}, timeout=(5, 60))
        status = r.status_code
        if status >= 400:
            return CheckResult("ollama_latency", ok=False, detail=f"HTTP {status}: {r.text[:300]}")
        data = r.json()
        content = (((data or {}).get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        return CheckResult("ollama_latency", ok=False, detail=f"Error llamando a Ollama (non-stream): {exc}")
    t1 = time.perf_counter()

    # 2) First-token latency (stream)
    first_token_ms: int | None = None
    tokens = 0
    try:
        t2 = time.perf_counter()
        with s.post(f"{host}/api/chat", json={**base_payload, "stream": True}, stream=True, timeout=(5, 60)) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(chunk_size=8192, decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                token = ((chunk.get("message") or {}).get("content") or "")
                if token:
                    tokens += 1
                    if first_token_ms is None:
                        first_token_ms = _ms(time.perf_counter() - t2)
                if chunk.get("done"):
                    break
    except Exception:
        # Streaming puede fallar en entornos concretos; no lo hacemos fatal si non-stream OK.
        first_token_ms = None

    detail = (
        f"model={model}\n"
        f"non_stream_ms={_ms(t1 - t0)}\n"
        f"non_stream_reply={content[:80]!r}\n"
        f"stream_first_token_ms={first_token_ms}\n"
        f"stream_tokens_chunks={tokens}"
    )
    ok = True
    return CheckResult("ollama_latency", ok=ok, detail=detail)


def check_openai_latency() -> CheckResult:
    """Mide latencia de OpenAI usando el SDK si está disponible."""
    provider = _safe_env("AI_PROVIDER").lower()
    if provider not in ("openai", "auto", ""):
        return CheckResult("openai_latency", ok=True, detail=f"AI_PROVIDER={provider} (saltando prueba OpenAI)")

    key = _safe_env("OPENAI_API_KEY")
    if not key:
        return CheckResult("openai_latency", ok=True, detail="OPENAI_API_KEY no configurada (saltando).")

    model = _safe_env("OPENAI_MODEL") or "gpt-5.5"
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        return CheckResult("openai_latency", ok=False, detail=f"No se pudo importar SDK openai: {exc}")

    client = OpenAI(api_key=key)
    t0 = time.perf_counter()
    try:
        # Respuesta corta, sin streaming; esto mide roundtrip real.
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Di solo: OK"}],
            temperature=0.0,
            max_tokens=16,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        return CheckResult("openai_latency", ok=False, detail=f"Error OpenAI request: {exc}")
    t1 = time.perf_counter()

    detail = f"model={model}\nnon_stream_ms={_ms(t1 - t0)}\nreply={text[:80]!r}"
    return CheckResult("openai_latency", ok=True, detail=detail)


def run_all(public_url: str = "") -> int:
    LOG_FILE.write_text("", encoding="utf-8")
    header("DIAGNOSTICO COMPLETO - Nexo")

    checks = [
        ("py_compile", check_py_compile),
        ("imports", check_imports),
        ("openai_config", check_openai_config),
        ("public_url", lambda: check_public_url(public_url)),
        ("openai_latency", check_openai_latency),
        ("ollama", check_ollama_basic),
        ("ollama_latency", check_ollama_latency),
        ("web_mode_responses", check_web_mode_responses),
    ]

    results: list[CheckResult] = []
    for name, fn in checks:
        section(f"CHECK: {name}")
        try:
            res = fn()
        except Exception as exc:
            res = CheckResult(name, ok=False, detail=str(exc))
        results.append(res)
        _w(("[OK] " if res.ok else "[ERROR] ") + res.name)
        if res.detail:
            _w(res.detail)

    section("RESUMEN")
    ok_count = sum(1 for r in results if r.ok)
    _w(f"OK={ok_count} ERROR={len(results)-ok_count}")
    for r in results:
        _w(("[OK] " if r.ok else "[ERROR] ") + r.name)

    _w("")
    _w(f"Log guardado en: {LOG_FILE}")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostico completo de Nexo")
    parser.add_argument("url", nargs="?", help="URL publica opcional, por ejemplo https://tu-dominio.ngrok-free.app")
    parser.add_argument("--public-url", dest="public_url", default="", help="URL publica a probar")
    args = parser.parse_args()
    raise SystemExit(run_all(args.public_url or args.url or ""))

