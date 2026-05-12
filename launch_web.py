from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
TOOLS_DIR = ROOT / "tools"
WEB_LOG = LOG_DIR / "web_app.log"
NGROK_LOG = LOG_DIR / "ngrok.log"
TUNNEL_LOG = LOG_DIR / "cloudflared.log"
LOCAL_CLOUDFLARED = TOOLS_DIR / "cloudflared.exe"
LOCAL_NGROK = TOOLS_DIR / "ngrok.exe"
SETTINGS_FILE = ROOT / "web_data" / "settings.json"

WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 7860
MAX_PORT = 7899
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
NGROK_ZIP_URL = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
PUBLIC_URL_RE = re.compile(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com")
NGROK_URL_RE = re.compile(
    r"https://[-a-zA-Z0-9.]+\.(?:ngrok-free\.app|ngrok-free\.dev|ngrok-free\.pizza|ngrok\.app|ngrok\.dev|ngrok\.pizza|ngrok\.io)"
)
ANY_HTTPS_URL_RE = re.compile(r"https://[^\s|\"'<>]+")
ORIGIN_ERROR_RE = re.compile(
    r"unable to reach the origin service|dial tcp 127\.0\.0\.1:\d+|conexi[oó]n denegada",
    re.IGNORECASE,
)

PERFORMANCE_DEFAULTS = {
    "IA_MODEL_PROFILE": "fast",
    "IA_OLLAMA_NUM_THREAD": "8",
    "IA_NUM_CTX_ARQUITECTO": "4096",
    "IA_NUM_CTX_PROGRAMADOR": "4096",
    "IA_NUM_BATCH_ARQUITECTO": "256",
    "IA_NUM_BATCH_PROGRAMADOR": "512",
    "IA_OLLAMA_KEEP_ALIVE": "45m",
}


def apply_performance_defaults(env: dict[str, str] | None = None) -> dict[str, str]:
    target = env if env is not None else os.environ
    for key, value in PERFORMANCE_DEFAULTS.items():
        target.setdefault(key, value)
    return target


def say(message: str = "") -> None:
    print(message, flush=True)


def python_command() -> list[str]:
    env_exe = os.getenv("NEXO_WEB_PY_EXE") or os.getenv("IA_WEB_PY_EXE")
    env_args = (os.getenv("NEXO_WEB_PY_ARGS") or os.getenv("IA_WEB_PY_ARGS", "")).split()
    if env_exe:
        return [env_exe, *env_args]

    if os.name == "nt" and "pythoncore-" in str(sys.executable).lower():
        wrapper = Path.home() / "AppData" / "Local" / "Python" / "bin" / "python.exe"
        if wrapper.exists():
            return [str(wrapper)]
        py_launcher = shutil.which("py")
        if py_launcher:
            return [py_launcher, "-3"]
    return [sys.executable]


def section(title: str) -> None:
    say()
    say("=" * 62)
    say(f" {title}")
    say("=" * 62)


def run(
    args: list[str],
    *,
    cwd: Path = ROOT,
    check: bool = False,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        detail = ""
        if capture:
            detail = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(f"Comando fallido ({result.returncode}): {command}\n{detail}")
    return result


def creation_flags(*, no_window: bool = True, new_console: bool = False) -> int:
    if os.name != "nt":
        return 0
    flags = subprocess.CREATE_NEW_PROCESS_GROUP
    if new_console:
        flags |= subprocess.CREATE_NEW_CONSOLE
    if no_window and not new_console:
        flags |= subprocess.CREATE_NO_WINDOW
    return flags


def safe_popen(*args, **kwargs) -> subprocess.Popen[bytes]:
    flags = kwargs.get("creationflags", 0)
    try:
        return subprocess.Popen(*args, **kwargs)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 740 and flags:
            say("[AVISO] Windows rechazo flags del proceso; reintentando sin flags.")
            kwargs["creationflags"] = 0
            return subprocess.Popen(*args, **kwargs)
        raise


def ensure_dirs() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    TOOLS_DIR.mkdir(exist_ok=True)


def append_log_header(path: Path, title: str) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write("\n")
        handle.write("=" * 78 + "\n")
        handle.write(f"{title} - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        handle.write("=" * 78 + "\n")


def reset_session_log(path: Path, title: str) -> None:
    path.parent.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    if path.exists():
        rotated = path.with_name(f"{path.stem}.{stamp}.prev{path.suffix}")
        try:
            path.replace(rotated)
            say(f"[INFO] Log previo rotado: {rotated.name}")
        except OSError:
            path.write_text("", encoding="utf-8")
    append_log_header(path, title)


def tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return f"No existe el log: {path}"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:]) or "(log vacio)"


def missing_imports() -> list[str]:
    required = [
        "flask",
        "waitress",
        "requests",
        "colorama",
        "openai",
        "dotenv",
        "ddgs",
        "bs4",
        "pypdf",
        "PIL",
        "cv2",
        "docx",
        "openpyxl",
        "pptx",
        "moviepy",
        "imageio_ffmpeg",
        "py7zr",
    ]
    return [name for name in required if importlib.util.find_spec(name) is None]


def ensure_dependencies() -> None:
    missing = missing_imports()
    if not missing:
        say("[OK] Dependencias web encontradas.")
        return

    requirements = ROOT / "requirements_web.txt"
    if not requirements.exists():
        raise RuntimeError("No existe requirements_web.txt.")

    say(f"[INFO] Faltan dependencias: {', '.join(missing)}")
    say("[INFO] Instalando dependencias web...")
    run(
        [
            *python_command(),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements),
        ],
        check=True,
    )
    missing_after = missing_imports()
    if missing_after:
        raise RuntimeError(
            "No se pudieron importar estas dependencias tras instalar: "
            + ", ".join(missing_after)
        )
    say("[OK] Dependencias instaladas.")


def ensure_ollama_and_models() -> None:
    say("[INFO] Verificando Ollama y modelos...")
    sys.path.insert(0, str(ROOT))
    from orchestrator import MODELS, is_model_installed, start_ollama

    if not start_ollama():
        raise RuntimeError("Ollama no pudo iniciarse.")

    required_roles = ["arquitecto", "programador"]
    missing = [MODELS[role] for role in required_roles if not is_model_installed(MODELS[role])]
    if missing:
        raise RuntimeError(
            "Faltan modelos requeridos para la web: "
            + ", ".join(missing)
            + "\nDescargalos con: ollama pull <modelo>"
        )
    say("[OK] Ollama listo y modelos requeridos instalados.")


def read_settings() -> dict[str, object]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def openai_key_configured() -> bool:
    if os.getenv("OPENAI_API_KEY", "").strip():
        return True
    key = str(read_settings().get("openai_api_key", "")).strip()
    return bool(key)


def ensure_ai_backend() -> None:
    if openai_key_configured():
        say("[OK] OpenAI configurado. Ollama queda como respaldo local si esta disponible.")
        return
    say("[INFO] No hay OPENAI_API_KEY configurada; usando Ollama como motor requerido.")
    ensure_ollama_and_models()


def ensure_login_configured() -> None:
    try:
        sys.path.insert(0, str(ROOT))
        from web_app import ensure_data_files, load_users_data

        ensure_data_files()
        data = load_users_data()
    except Exception as exc:
        raise RuntimeError(f"No se pudo preparar el registro de usuarios: {exc}") from exc

    count = len(data.get("users", []))
    say(f"[OK] Registro abierto. Cuentas existentes: {count}.")


def local_port_from_netstat(value: str) -> int | None:
    try:
        return int(value.rsplit(":", 1)[1])
    except Exception:
        return None


def listening_pid(port: int) -> int | None:
    try:
        result = run(["netstat", "-ano", "-p", "tcp"], capture=True)
    except Exception:
        return None

    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_addr = parts[1]
        state = parts[3].upper()
        pid = parts[-1]
        if state != "LISTENING" or local_port_from_netstat(local_addr) != port:
            continue
        try:
            return int(pid)
        except ValueError:
            return None
    return None


def process_command_line(pid: int) -> str:
    if os.name != "nt":
        return ""

    ps = shutil.which("powershell") or shutil.which("powershell.exe")
    if ps:
        command = (
            f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine"
        )
        result = run(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    wmic = shutil.which("wmic")
    if wmic:
        result = run(
            [
                wmic,
                "process",
                "where",
                f"ProcessId={pid}",
                "get",
                "CommandLine",
                "/value",
            ],
            capture=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()

    return ""


def terminate_pid(pid: int, *, reason: str = "") -> bool:
    details = f" ({reason})" if reason else ""
    try:
        result = run(["taskkill", "/PID", str(pid), "/T", "/F"], capture=True)
        if result.returncode == 0:
            say(f"[INFO] Proceso {pid} finalizado{details}.")
            return True
        say(f"[AVISO] No se pudo finalizar PID {pid}{details}.")
    except Exception as exc:
        say(f"[AVISO] Error al finalizar PID {pid}{details}: {exc}")
    return False


def process_responds_as_web(port: int, *, timeout: float = 2.5) -> bool:
    urls = [f"http://{WEB_HOST}:{port}/login", f"http://{WEB_HOST}:{port}/"]
    for url in urls:
        if http_ok(url, timeout=timeout):
            return True
    return False


def port_accepts_connection(port: int) -> bool:
    try:
        with socket.create_connection((WEB_HOST, port), timeout=0.35):
            return True
    except OSError:
        return False


def find_free_web_port(start: int = DEFAULT_WEB_PORT + 1) -> int:
    for port in range(start, MAX_PORT + 1):
        if listening_pid(port) is None and not port_accepts_connection(port):
            return port
    raise RuntimeError(f"No hay puertos libres entre {start} y {MAX_PORT}.")


def choose_web_port() -> tuple[int, bool, int | None, str]:
    pid = listening_pid(DEFAULT_WEB_PORT)
    if pid:
        command_line = process_command_line(pid)
        if "web_app.py" in command_line.lower():
            return DEFAULT_WEB_PORT, True, pid, command_line

        return find_free_web_port(), False, None, ""

    return DEFAULT_WEB_PORT, False, None, ""


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def start_web_server(port: int) -> subprocess.Popen[bytes]:
    append_log_header(WEB_LOG, f"web_app.py puerto {port}")
    env = os.environ.copy()
    env["WEB_HOST"] = WEB_HOST
    env["WEB_PORT"] = str(port)
    env["WEB_SESSION_SECURE"] = "0"
    apply_performance_defaults(env)

    log_handle = WEB_LOG.open("ab")
    try:
        process = safe_popen(
            [
                *python_command(),
                "web_app.py",
                "--host",
                WEB_HOST,
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags(no_window=True),
        )
    finally:
        log_handle.close()
    return process


def wait_for_web(port: int, process: subprocess.Popen[bytes] | None) -> bool:
    url = f"http://{WEB_HOST}:{port}/"
    for _ in range(30):
        if http_ok(url):
            return True
        if process is not None and process.poll() is not None:
            break
        time.sleep(1)
    return False


def web_supports_registration(port: int) -> bool:
    return http_ok(f"http://{WEB_HOST}:{port}/register")


def validate_or_recover_existing_web(
    port: int,
    pid: int | None,
    command_line: str,
) -> tuple[bool, bool]:
    if pid is None:
        return False, False

    if process_responds_as_web(port):
        return True, False

    say(
        f"[AVISO] Detectado web_app.py en {port} (PID {pid}) pero no responde por HTTP "
        "(/login o /). Se reiniciara limpio."
    )
    killed = terminate_pid(pid, reason="web_app.py no responde")
    for _ in range(5):
        if listening_pid(port) is None:
            break
        time.sleep(0.4)
    still_listening = listening_pid(port) is not None
    if still_listening:
        say(
            f"[AVISO] El puerto {port} sigue ocupado tras cerrar PID {pid}. "
            "Se usara un puerto alternativo."
        )
    return False, killed


def find_existing_registration_web() -> tuple[int, bool, int | None, str] | None:
    for port in range(DEFAULT_WEB_PORT, MAX_PORT + 1):
        pid = listening_pid(port)
        if not pid:
            continue
        command_line = process_command_line(pid)
        if "web_app.py" not in command_line.lower():
            continue
        if web_supports_registration(port):
            return port, True, pid, command_line
    return None


def local_origin_ready(port: int, *, timeout: float = 2.0) -> bool:
    return process_responds_as_web(port, timeout=timeout)


def wait_for_local_origin(port: int, *, timeout_seconds: int = 40) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if local_origin_ready(port):
            return True
        time.sleep(1)
    return False


def cleanup_previous_project_tunnels() -> None:
    enabled = (os.getenv("NEXO_CLEAN_PREVIOUS_TUNNELS") or "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        say("[INFO] Limpieza previa de tuneles desactivada por entorno.")
        return

    ps = shutil.which("powershell") or shutil.which("powershell.exe")
    if not ps:
        return

    process_filter = "@('ngrok.exe')" if is_ngrok_only_mode() else "@('cloudflared.exe','ngrok.exe')"
    command = (
        "$procs = Get-CimInstance Win32_Process | Where-Object { "
        f"$_.Name -in {process_filter} }}; "
        "$rows = foreach ($p in $procs) { "
        "$cmd = ($p.CommandLine -replace \"`r|`n\", \" \"); "
        "if ($cmd -match '127\\.0\\.0\\.1:7[0-9]{3}' -or $cmd -match 'web_app\\.py' -or $cmd -match 'IA combinada completo-EXPERIMENTAL') { "
        "\"$($p.ProcessId)|$($p.Name)|$cmd\" } }; "
        "$rows -join \"`n\""
    )
    result = run(
        [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture=True,
    )
    if result.returncode != 0:
        return

    victims: list[tuple[int, str]] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0].strip())
        except ValueError:
            continue
        name = parts[1].strip()
        victims.append((pid, name))

    if not victims:
        return

    say(f"[INFO] Limpieza previa: cerrando {len(victims)} proceso(s) de tunel antiguos.")
    for pid, name in victims:
        terminate_pid(pid, reason=f"limpieza previa {name}")


def download_cloudflared() -> Path:
    say("[INFO] cloudflared no esta en PATH ni en tools\\. Descargando...")
    temp_file = LOCAL_CLOUDFLARED.with_suffix(".download")
    if temp_file.exists():
        temp_file.unlink()

    try:
        with urllib.request.urlopen(CLOUDFLARED_URL, timeout=180) as response:
            with temp_file.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        temp_file.replace(LOCAL_CLOUDFLARED)
    except Exception as exc:
        if temp_file.exists():
            temp_file.unlink()
        raise RuntimeError(
            "No se pudo descargar cloudflared.\n"
            f"URL usada: {CLOUDFLARED_URL}\n"
            f"Error: {exc}"
        ) from exc

    say(f"[OK] cloudflared descargado en {LOCAL_CLOUDFLARED}")
    return LOCAL_CLOUDFLARED


def find_cloudflared() -> Path:
    if LOCAL_CLOUDFLARED.exists():
        say(f"[OK] Usando cloudflared local: {LOCAL_CLOUDFLARED}")
        return LOCAL_CLOUDFLARED

    found = shutil.which("cloudflared")
    if found:
        say(f"[OK] Usando cloudflared de PATH: {found}")
        return Path(found)

    return download_cloudflared()


def print_cloudflared_version(exe: Path) -> None:
    result = run([str(exe), "--version"], capture=True)
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0 and output:
        say(f"[OK] {output.splitlines()[0]}")
    elif result.returncode != 0:
        raise RuntimeError(f"cloudflared no se pudo ejecutar: {result.stderr}")


def find_ngrok() -> Path | None:
    env_exe = (os.getenv("NEXO_NGROK_EXE") or os.getenv("IA_NGROK_EXE") or os.getenv("NGROK_EXE") or "").strip()
    candidates: list[Path] = []
    if env_exe:
        candidates.append(Path(env_exe))
    candidates.append(LOCAL_NGROK)

    found = shutil.which("ngrok")
    if found:
        candidates.append(Path(found))

    home = Path.home()
    candidates.extend(
        [
            home / "AppData" / "Local" / "ngrok" / "ngrok.exe",
            home / "AppData" / "Roaming" / "ngrok" / "ngrok.exe",
            home / "scoop" / "apps" / "ngrok" / "current" / "ngrok.exe",
            Path("C:/ProgramData/chocolatey/bin/ngrok.exe"),
        ]
    )

    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        winget_packages = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
        try:
            candidates.extend(winget_packages.glob("Ngrok.Ngrok_*/ngrok.exe"))
        except OSError:
            pass

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def can_prompt() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def ask_yes_no(prompt: str, default_yes: bool = False) -> bool:
    if not can_prompt():
        return default_yes
    default_hint = "S/n" if default_yes else "s/N"
    answer = input(f"{prompt} [{default_hint}]: ").strip().lower()
    if not answer:
        return default_yes
    return answer in {"s", "si", "y", "yes"}


def download_ngrok() -> Path:
    say("[INFO] ngrok no instalado. Descargando binario oficial para Windows amd64...")
    temp_zip = LOCAL_NGROK.with_suffix(".zip.download")
    temp_dir = TOOLS_DIR / "ngrok_extract_tmp"
    if temp_zip.exists():
        temp_zip.unlink()
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(NGROK_ZIP_URL, timeout=180) as response:
            with temp_zip.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        with zipfile.ZipFile(temp_zip) as archive:
            archive.extractall(temp_dir)
        extracted = temp_dir / "ngrok.exe"
        if not extracted.exists():
            raise RuntimeError("No se encontro ngrok.exe dentro del ZIP descargado.")
        extracted.replace(LOCAL_NGROK)
        say(f"[OK] ngrok descargado en {LOCAL_NGROK}")
        return LOCAL_NGROK
    except Exception as exc:
        raise RuntimeError(
            "No se pudo descargar/instalar ngrok automaticamente.\n"
            f"URL usada: {NGROK_ZIP_URL}\n"
            f"Error: {exc}"
        ) from exc
    finally:
        if temp_zip.exists():
            temp_zip.unlink()
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def ensure_ngrok_available() -> Path:
    ngrok = find_ngrok()
    if ngrok:
        return ngrok

    auto_install = (os.getenv("NEXO_AUTO_INSTALL_NGROK") or "").strip().lower() in {"1", "true", "yes", "on"}
    if auto_install:
        ngrok = download_ngrok()
        print_ngrok_version(ngrok)
        return ngrok

    if ask_yes_no("ngrok no instalado. Quieres que lo descargue ahora en tools\\ngrok.exe?", default_yes=False):
        ngrok = download_ngrok()
        print_ngrok_version(ngrok)
        return ngrok

    raise RuntimeError(
        "ngrok no instalado para este lanzador (modo ngrok-only).\n"
        "Instalacion rapida:\n"
        "  1) Ejecuta de nuevo con NEXO_AUTO_INSTALL_NGROK=1\n"
        "  2) O coloca ngrok.exe en tools\\ngrok.exe\n"
        "  3) O instala ngrok en PATH (winget install ngrok.ngrok)"
    )


def print_ngrok_version(exe: Path) -> None:
    result = run(build_ngrok_command(exe, "version"), capture=True)
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0 and output:
        say(f"[OK] {output.splitlines()[0]}")
    elif result.returncode != 0:
        raise RuntimeError(f"ngrok no se pudo ejecutar: {result.stderr}")


def ensure_ngrok_authtoken(exe: Path) -> bool:
    token = (
        os.getenv("NEXO_NGROK_AUTHTOKEN")
        or os.getenv("NGROK_AUTHTOKEN")
        or ""
    ).strip()
    if not token:
        say("[AVISO] ngrok instalado pero no autenticado (sin NGROK_AUTHTOKEN/NEXO_NGROK_AUTHTOKEN).")
        say("[AVISO] Se intentara igual, pero el plan gratuito sin token tiene limites mas estrictos.")
        return False
    result = run(build_ngrok_command(exe, "config", "add-authtoken", token), capture=True)
    if result.returncode == 0:
        say("[OK] ngrok autenticado (authtoken aplicado/verificado).")
        return True
    say("[AVISO] No se pudo aplicar authtoken de ngrok; se intentara arrancar sin autenticar.")
    detail = (result.stdout or result.stderr or "").strip()
    if detail:
        say(detail.splitlines()[-1])
    return False


def normalize_public_url(value: str) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    lowered = text.lower()
    if not (lowered.startswith("https://") or lowered.startswith("http://")):
        return ""
    if ".ngrok" not in lowered:
        return ""
    return text.rstrip("/")


def build_ngrok_command(exe: Path, *extra_args: str) -> list[str]:
    if os.name == "nt" and exe.suffix.lower() in {".cmd", ".bat"}:
        return ["cmd", "/c", str(exe), *extra_args]
    return [str(exe), *extra_args]


def configured_ngrok_url() -> str:
    for name in ("NEXO_NGROK_URL", "NEXO_NGROK_DOMAIN", "IA_NGROK_URL", "IA_NGROK_DOMAIN", "NGROK_URL", "NGROK_DOMAIN"):
        value = normalize_public_url(os.getenv(name) or "")
        if value:
            return value

    url_file = ROOT / "web_data" / "ngrok_url.txt"
    if url_file.exists():
        try:
            value = normalize_public_url(url_file.read_text(encoding="utf-8", errors="replace").splitlines()[0])
            if value:
                return value
        except Exception:
            pass

    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                for key in ("ngrok_url", "ngrok_domain"):
                    value = normalize_public_url(str(data.get(key) or ""))
                    if value:
                        return value
        except Exception:
            pass
    return ""


def ngrok_fixed_url_disabled_by_env() -> bool:
    value = (os.getenv("NEXO_NGROK_NO_FIXED_URL") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def ngrok_log_indicates_paid_custom_domain(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    paid_markers = (
        "err_ngrok_313",
        "custom subdomain",
        "custom domains are a paid feature",
        "reserved domain",
        "requires a paid plan",
        "paid plan",
    )
    return any(marker in lowered for marker in paid_markers)


def log_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def read_log_since(path: Path, start_pos: int) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, start_pos))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def start_cloudflared_tunnel(exe: Path, port: int) -> tuple[subprocess.Popen[bytes], int]:
    append_log_header(TUNNEL_LOG, f"cloudflared puerto {port}")
    start_pos = log_size(TUNNEL_LOG)
    log_handle = TUNNEL_LOG.open("ab")
    try:
        process = safe_popen(
            [
                str(exe),
                "tunnel",
                "--no-autoupdate",
                "--edge-ip-version",
                "4",
                "--retries",
                "15",
                "--url",
                f"http://127.0.0.1:{port}",
            ],
            cwd=str(ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags(no_window=True),
        )
    finally:
        log_handle.close()
    return process, start_pos


def start_ngrok_tunnel(
    exe: Path, port: int, *, use_fixed_url: bool = True
) -> tuple[subprocess.Popen[bytes], int, str]:
    reset_session_log(NGROK_LOG, f"ngrok puerto {port}")
    start_pos = log_size(NGROK_LOG)
    fixed_url = configured_ngrok_url() if use_fixed_url else ""
    args = build_ngrok_command(exe, "http", f"http://127.0.0.1:{port}", "--log=stdout")
    if fixed_url:
        args.extend(["--url", fixed_url])
        say(f"[INFO] ngrok usara URL fija: {fixed_url}")
    elif use_fixed_url:
        say("[INFO] ngrok usara URL aleatoria (sin URL fija configurada).")
    else:
        say("[INFO] ngrok forzado a URL aleatoria (sin URL fija).")
    log_handle = NGROK_LOG.open("ab")
    try:
        process = safe_popen(
            args,
            cwd=str(ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=None,
            creationflags=creation_flags(no_window=False, new_console=True),
        )
    finally:
        log_handle.close()
    return process, start_pos, fixed_url


def _ngrok_url_from_api() -> str | None:
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:4040/api/tunnels",
            headers={"User-Agent": "Nexo-Launcher/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            for t in data.get("tunnels", []):
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    return url
    except Exception:
        pass
    return None


def wait_for_public_url(
    process: subprocess.Popen[bytes],
    log_path: Path,
    url_re: re.Pattern[str],
    start_pos: int,
    timeout_seconds: int = 75,
) -> str | None:
    for _ in range(timeout_seconds):
        url = _ngrok_url_from_api()
        if url:
            return url
        text = read_log_since(log_path, start_pos)
        matches = [match.group(0) for match in url_re.finditer(text)]
        if matches:
            return matches[-1]
        if process.poll() is not None:
            break
        time.sleep(0.5)
    return None


def best_ngrok_url_from_log(text: str) -> str | None:
    candidates = [match.group(0).rstrip('",') for match in ANY_HTTPS_URL_RE.finditer(text)]
    for url in reversed(candidates):
        if ".ngrok" in url:
            return url
    return None


def public_url_ready(url: str) -> bool:
    base = url.rstrip("/")
    candidates = [base + "/login", base + "/"]
    headers = {"User-Agent": "Nexo-Launcher/1.0", "ngrok-skip-browser-warning": "1"}
    for test_url in candidates:
        request = urllib.request.Request(test_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            continue
    return False


def wait_for_public_web(url: str, *, max_wait_seconds: int = 180) -> bool:
    deadline = time.time() + max_wait_seconds
    sleep_s = 1.0
    while time.time() < deadline:
        if public_url_ready(url):
            return True
        time.sleep(sleep_s)
        sleep_s = min(12.0, sleep_s * 1.4)
    return False


def stop_started_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
    except Exception:
        pass


def tunnel_order() -> list[str]:
    desired = (os.getenv("NEXO_TUNNEL") or os.getenv("IA_TUNNEL") or "auto").strip().lower()
    if desired in {"none", "off", "0", "duckdns", "nodns", "no"}:
        return []
    if desired in {"ngrok"}:
        return ["ngrok"]
    return ["cloudflared"]


def is_ngrok_only_mode() -> bool:
    return tunnel_order() == ["ngrok"]


def start_public_tunnel(port: int) -> tuple[str, subprocess.Popen[bytes], str, Path] | None:
    last_log = TUNNEL_LOG
    for provider in tunnel_order():
        process: subprocess.Popen[bytes] | None = None
        start_pos = 0
        try:
            if provider == "cloudflared":
                cloudflared = find_cloudflared()
                print_cloudflared_version(cloudflared)
                say("[INFO] Arrancando Cloudflare Quick Tunnel...")
                process, start_pos = start_cloudflared_tunnel(cloudflared, port)
                public_url = wait_for_public_url(process, TUNNEL_LOG, PUBLIC_URL_RE, start_pos)
                last_log = TUNNEL_LOG
            elif provider == "ngrok":
                ngrok = ensure_ngrok_available()
                print_ngrok_version(ngrok)
                ensure_ngrok_authtoken(ngrok)
                say("[INFO] Arrancando ngrok...")
                disable_fixed_url = ngrok_fixed_url_disabled_by_env()
                use_fixed_url = not disable_fixed_url
                if disable_fixed_url:
                    say("[INFO] NEXO_NGROK_NO_FIXED_URL=1: se ignora cualquier URL fija configurada.")

                retried_without_fixed = False
                while True:
                    process, start_pos, fixed_url = start_ngrok_tunnel(
                        ngrok, port, use_fixed_url=use_fixed_url
                    )
                    if fixed_url:
                        logged_url = wait_for_public_url(
                            process, NGROK_LOG, ANY_HTTPS_URL_RE, start_pos, timeout_seconds=8
                        )
                        recent_text = read_log_since(NGROK_LOG, start_pos)
                        if ngrok_log_indicates_paid_custom_domain(recent_text):
                            public_url = ""
                        elif process.poll() is not None:
                            public_url = logged_url or ""
                        else:
                            public_url = logged_url or fixed_url
                    else:
                        public_url = wait_for_public_url(process, NGROK_LOG, NGROK_URL_RE, start_pos)
                        if not public_url:
                            public_url = best_ngrok_url_from_log(read_log_since(NGROK_LOG, start_pos))

                    if public_url:
                        break

                    recent_text = read_log_since(NGROK_LOG, start_pos)
                    paid_domain_error = ngrok_log_indicates_paid_custom_domain(recent_text)
                    can_retry_without_fixed = fixed_url and (not retried_without_fixed) and paid_domain_error
                    if not can_retry_without_fixed:
                        break

                    retried_without_fixed = True
                    use_fixed_url = False
                    say(
                        "[AVISO] ngrok rechazo la URL fija: los subdominios/custom domains fijos "
                        "requieren plan pago (ERR_NGROK_313)."
                    )
                    say("[INFO] Reintentando automaticamente una vez con URL aleatoria...")
                    stop_started_process(process)
                    process = None
                last_log = NGROK_LOG
            else:
                continue
        except Exception as exc:
            if provider == "ngrok" and is_ngrok_only_mode():
                say(f"[ERROR] ngrok no instalado o fallo al iniciar en modo ngrok-only: {exc}")
                stop_started_process(process)
                return None
            say(f"[AVISO] No se pudo usar {provider}: {exc}")
            stop_started_process(process)
            continue

        if not public_url:
            recent_text = read_log_since(last_log, start_pos) if process is not None else ""
            if recent_text and ORIGIN_ERROR_RE.search(recent_text):
                say(
                    "[ERROR] El tunel no pudo conectar al origen local "
                    f"http://127.0.0.1:{port} (origen local no responde)."
                )
            say(f"[ERROR] {provider} arranco pero URL no disponible dentro del tiempo esperado.")
            stop_started_process(process)
            if provider == "ngrok" and is_ngrok_only_mode():
                say("[ERROR] Modo ngrok-only: no hay fallback a cloudflared.")
                return None
            continue

        say(f"[INFO] Comprobando URL publica de {provider} (puede tardar)...")
        if wait_for_public_web(public_url, max_wait_seconds=60):
            return provider, process, public_url, last_log

        if process is not None and process.poll() is None:
            say(
                f"[AVISO] La URL de {provider} aun no responde, pero el tunel sigue activo. "
                "Continuando (puede tardar 1-3 min en estar reachable)."
            )
            return provider, process, public_url, last_log

        say(f"[AVISO] La URL de {provider} no respondio y el tunel se detuvo. Probando alternativa si existe...")
        stop_started_process(process)
        if provider == "ngrok" and is_ngrok_only_mode():
            say("[ERROR] Modo ngrok-only: ngrok se detuvo y no hay fallback.")
            return None

    return None


def main() -> int:
    os.chdir(ROOT)
    ensure_dirs()
    apply_performance_defaults()

    section("Nexo - Lanzador Web Todo En Uno")
    say(f"Python: {' '.join(python_command())}")
    say(f"Proyecto: {ROOT}")
    say(f"Logs: {LOG_DIR}")

    try:
        section("Comprobaciones")
        ensure_dependencies()
        ensure_ai_backend()
        ensure_login_configured()

        section("Servidor web")
        existing_web = find_existing_registration_web()
        if existing_web:
            port, reuse, pid, command_line = existing_web
        else:
            port, reuse, pid, command_line = choose_web_port()
        web_process: subprocess.Popen[bytes] | None = None
        if reuse:
            healthy_reuse, _ = validate_or_recover_existing_web(port, pid, command_line)
            if healthy_reuse and web_supports_registration(port):
                say(f"[OK] Reutilizando web_app.py existente en puerto {port} (PID {pid}).")
                if command_line:
                    say(f"[INFO] {command_line}")
            else:
                old_port = port
                current_pid = listening_pid(old_port)
                if current_pid:
                    port = find_free_web_port()
                else:
                    port = old_port
                reuse = False
                say(
                    f"[INFO] Arrancando una instancia limpia de web_app.py en {port} "
                    f"(anterior detectada en {old_port})."
                )
                say("[INFO] Arrancando servidor web...")
                web_process = start_web_server(port)
        if not reuse and web_process is None:
            if port != DEFAULT_WEB_PORT:
                say(
                    f"[INFO] Puerto {DEFAULT_WEB_PORT} ocupado por otro proceso. "
                    f"Usando {port}."
                )
            say("[INFO] Arrancando servidor web...")
            web_process = start_web_server(port)

        if not wait_for_web(port, web_process):
            say("[ERROR] La web no respondio a /login.")
            say()
            say(f"Ultimas lineas de {WEB_LOG}:")
            say(tail(WEB_LOG))
            return 1

        local_url = f"http://localhost:{port}"
        say(f"[OK] Web lista: {local_url}")

        section("Health-check origen local")
        say("[INFO] Verificando origen local antes de abrir tunel...")
        if not wait_for_local_origin(port, timeout_seconds=40):
            say(
                "[ERROR] Origen local no responde en "
                f"http://127.0.0.1:{port}/login ni / tras reintentos."
            )
            say()
            say(f"Ultimas lineas de {WEB_LOG}:")
            say(tail(WEB_LOG))
            return 1
        say("[OK] Origen local responde correctamente.")

        section("Tunel publico")
        no_tunnel_mode = tunnel_order() == []
        tunnel_log = NGROK_LOG
        if no_tunnel_mode:
            say("[INFO] Modo sin tunel (NEXO_TUNNEL=duckdns). Se omite ngrok/cloudflared.")
            say(f"[OK] Web disponible localmente en: {local_url}")
        else:
            cleanup_previous_project_tunnels()
            tunnel = start_public_tunnel(port)
            if not tunnel:
                say("[ERROR] No se pudo crear un tunel publico que respondiera.")
                if not local_origin_ready(port):
                    say("[ERROR] Diagnostico: el origen local no responde; no es un fallo del tunel.")
                say()
                say(f"URL LOCAL: {local_url}")
                if not is_ngrok_only_mode():
                    say()
                    say(f"Ultimas lineas de {TUNNEL_LOG}:")
                    say(tail(TUNNEL_LOG))
                say()
                say(f"Ultimas lineas de {NGROK_LOG}:")
                say(tail(NGROK_LOG))
                return 1
            tunnel_provider, tunnel_process, public_url, tunnel_log = tunnel

        section("Listo")
        say(f"URL LOCAL:   {local_url}")
        if not no_tunnel_mode:
            say(f"URL PUBLICA: {public_url} ({tunnel_provider})")
        say()
        say(f"Log web:    {WEB_LOG}")
        if not no_tunnel_mode:
            say(f"Log tunel:  {tunnel_log}")
        say()
        section("Pruebas rapidas (web UI)")
        say("- Entra a la web y manda: 'hola', 'nada xd', 'bien y tu?'.")
        say("  Esperado: respuesta conversacional (sin pipeline de codigo) y sin busqueda web.")
        say("- Prueba streaming: la respuesta debe aparecer UNA vez (no duplicada) mientras se escribe.")
        say("- Gate web: manda 'busca en internet: precio del dolar hoy' y confirma que solo ahi usa web.")
        say("  Luego manda 'precio del dolar' (sin 'hoy' / sin pedir web) y confirma que NO dispara web.")
        say()
        say("Puedes cerrar esta ventana; la web y el tunel quedan ejecutandose.")
        return 0

    except KeyboardInterrupt:
        say()
        say("[INFO] Cancelado por el usuario.")
        return 130
    except Exception as exc:
        say()
        say("[ERROR] " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())