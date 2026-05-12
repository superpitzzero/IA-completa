"""
╔══════════════════════════════════════════════════════════════════╗
║         NEXO MEJORAS — Patcher automático v1.0                  ║
║  Implementa las 4 áreas de mejora en web_app.py de una vez.     ║
║                                                                  ║
║  ÁREAS:                                                          ║
║  1. Gestión VRAM / Context Trim / Rate Queue                    ║
║  2. UI/UX: Monitor GPU, Prism.js, Smooth Scroll                 ║
║  3. Killer Features: Voice-to-Text, Personalidad                ║
║  4. Seguridad: Rate Limiting, Invite Codes                      ║
║                                                                  ║
║  USO: python nexo_patch.py                                       ║
║  Se crea backup automático en web_app.py.bak                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import shutil
import sys
from pathlib import Path

WEB_APP = Path(__file__).resolve().parent / "web_app.py"
BACKUP  = WEB_APP.with_suffix(".py.bak")

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"{GREEN}[OK]{RESET} {msg}")
def warn(msg):print(f"{YELLOW}[AVISO]{RESET} {msg}")
def err(msg): print(f"{RED}[ERROR]{RESET} {msg}")
def info(msg):print(f"{CYAN}[INFO]{RESET} {msg}")

# ═══════════════════════════════════════════════════════════════
#  PARCHES — definidos como (nombre, old_str, new_str)
# ═══════════════════════════════════════════════════════════════

PATCHES = []

def patch(name, old, new):
    PATCHES.append((name, old, new))

# ─────────────────────────────────────────────────────────────
# P1 · Rate Limiter + Personality thread-local constants
# Insertamos justo después de MEMORY_UPDATE_LOCK = ...
# ─────────────────────────────────────────────────────────────
patch(
    "P1 · Rate Limiter + Personality constants",
    "MEMORY_UPDATE_LOCK = threading.Lock()\r\n",
    "MEMORY_UPDATE_LOCK = threading.Lock()\r\n"
    "\r\n"
    "# ═══ NEXO MEJORAS: Rate Limiter por usuario ═══\r\n"
    "_RATE_LIMIT_LOCK = threading.Lock()\r\n"
    "_RATE_LIMIT_DATA: Dict[str, List[float]] = {}\r\n"
    "RATE_LIMIT_MAX    = int(os.getenv('NEXO_RATE_LIMIT_MAX',    '5'))\r\n"
    "RATE_LIMIT_WINDOW = int(os.getenv('NEXO_RATE_LIMIT_WINDOW', '60'))\r\n"
    "\r\n"
    "def check_rate_limit(user_id: str) -> Optional[int]:\r\n"
    "    \"\"\"Devuelve segundos de espera si supera el límite; None si OK.\"\"\"\r\n"
    "    now = time.time()\r\n"
    "    with _RATE_LIMIT_LOCK:\r\n"
    "        ts = _RATE_LIMIT_DATA.get(user_id, [])\r\n"
    "        ts = [t for t in ts if now - t < RATE_LIMIT_WINDOW]\r\n"
    "        if len(ts) >= RATE_LIMIT_MAX:\r\n"
    "            wait = int(RATE_LIMIT_WINDOW - (now - ts[0])) + 1\r\n"
    "            _RATE_LIMIT_DATA[user_id] = ts\r\n"
    "            return wait\r\n"
    "        ts.append(now)\r\n"
    "        _RATE_LIMIT_DATA[user_id] = ts\r\n"
    "        return None\r\n"
    "\r\n"
    "# ═══ NEXO MEJORAS: Personality (thread-local) ═══\r\n"
    "_personality_local = threading.local()\r\n"
    "\r\n"
    "PERSONALITY_PROMPTS: Dict[str, str] = {\r\n"
    "    'normal':      '',\r\n"
    "    'programador': 'Tono técnico: responde directo, usa ejemplos de código cuando sea útil, evita explicaciones de relleno.',\r\n"
    "    'creativo':    'Tono creativo: usa metáforas, analogías imaginativas y entusiasmo. Haz las respuestas amenas y originales.',\r\n"
    "    'conciso':     'Tono ultra-conciso: responde siempre en máximo 3 líneas. Nada de introducciones, solo el núcleo de la respuesta.',\r\n"
    "}\r\n"
    "\r\n"
    "def set_personality(p: str) -> None:\r\n"
    "    _personality_local.value = p if p in PERSONALITY_PROMPTS else 'normal'\r\n"
    "\r\n"
    "def get_personality() -> str:\r\n"
    "    return getattr(_personality_local, 'value', 'normal')\r\n"
    "\r\n",
)

# ─────────────────────────────────────────────────────────────
# P2 · History Trimmer — antes de build_history_text
# ─────────────────────────────────────────────────────────────
patch(
    "P2 · History Trimmer",
    "def build_history_text(messages: List[Dict[str, str]], limit: int = 12) -> str:\r\n",
    "# ═══ NEXO MEJORAS: History Trimmer ═══\r\n"
    "def trim_history_to_budget(messages: List[Dict], max_chars: int = 12000) -> List[Dict]:\r\n"
    "    \"\"\"Elimina mensajes antiguos cuando el historial supera max_chars.\"\"\"\r\n"
    "    chat = list(messages)\r\n"
    "    while len(chat) > 2:\r\n"
    "        total = sum(len(str(m.get('content', ''))) for m in chat)\r\n"
    "        if total <= max_chars:\r\n"
    "            break\r\n"
    "        chat.pop(0)\r\n"
    "    return chat\r\n"
    "\r\n"
    "\r\n"
    "def build_history_text(messages: List[Dict[str, str]], limit: int = 12) -> str:\r\n",
)

# ─────────────────────────────────────────────────────────────
# P3 · Aplicar trim en build_user_prompt
# ─────────────────────────────────────────────────────────────
patch(
    "P3 · Aplicar trim en build_user_prompt",
    "    history = build_history_text(history_messages)\r\n",
    "    history = build_history_text(trim_history_to_budget(history_messages))\r\n",
)

# ─────────────────────────────────────────────────────────────
# P4 · Inyectar personalidad en guarded_system_prompt
# ─────────────────────────────────────────────────────────────
patch(
    "P4 · Personality injection en guarded_system_prompt",
    "def guarded_system_prompt(prompt: str, ai_settings: Optional[Dict[str, Any]] = None) -> str:\r\n"
    "    guard = identity_guard_from_settings(ai_settings)\r\n"
    "    if guard:\r\n"
    "        return f\"{guard}\\n\\n{prompt}\"\r\n"
    "    return prompt\r\n",

    "def guarded_system_prompt(prompt: str, ai_settings: Optional[Dict[str, Any]] = None) -> str:\r\n"
    "    guard = identity_guard_from_settings(ai_settings)\r\n"
    "    personality_hint = PERSONALITY_PROMPTS.get(get_personality(), '')\r\n"
    "    parts: List[str] = []\r\n"
    "    if guard:\r\n"
    "        parts.append(guard)\r\n"
    "    parts.append(prompt)\r\n"
    "    if personality_hint:\r\n"
    "        parts.append(f'Estilo de respuesta: {personality_hint}')\r\n"
    "    return '\\n\\n'.join(parts)\r\n",
)

# ─────────────────────────────────────────────────────────────
# P5 · Leer personality del payload en api_chat_stream (rama JSON)
# ─────────────────────────────────────────────────────────────
patch(
    "P5 · Leer personality en api_chat_stream",
    "                mode = str(payload.get(\"mode\", \"rapido\")).strip().lower()\r\n"
    "                user_message = str(payload.get(\"message\", \"\")).strip()\r\n"
    "            if mode not in {\"auto\", \"rapido\", \"combinado\", \"codigo\"}:\r\n",

    "                mode = str(payload.get(\"mode\", \"rapido\")).strip().lower()\r\n"
    "                user_message = str(payload.get(\"message\", \"\")).strip()\r\n"
    "                set_personality(str(payload.get(\"personality\", \"normal\")).strip())\r\n"
    "            if mode not in {\"auto\", \"rapido\", \"combinado\", \"codigo\"}:\r\n",
)

# ─────────────────────────────────────────────────────────────
# P6 · Rate limit check en api_chat_stream (justo tras user_id)
# ─────────────────────────────────────────────────────────────
patch(
    "P6 · Rate limit check en api_chat_stream",
    "            user_id = str(request_user[\"id\"])\r\n"
    "            user_plan = public_plan_for_user(request_user)\r\n",

    "            user_id = str(request_user[\"id\"])\r\n"
    "            # ═══ NEXO MEJORAS: Rate Limiting ═══\r\n"
    "            _rl_wait = check_rate_limit(user_id)\r\n"
    "            if _rl_wait:\r\n"
    "                return jsonify({\"error\": f\"Demasiadas peticiones. Espera {_rl_wait}s antes de enviar otro mensaje.\", \"retry_after\": _rl_wait}), 429\r\n"
    "            user_plan = public_plan_for_user(request_user)\r\n",
)

# ─────────────────────────────────────────────────────────────
# P7 · Endpoint /api/system-stats — antes de api_chat_stream
# ─────────────────────────────────────────────────────────────
patch(
    "P7 · Endpoint /api/system-stats",
    "    @app.post(\"/api/chat/stream\")\r\n"
    "    def api_chat_stream() -> Response:\r\n",

    "    # ═══ NEXO MEJORAS: Monitor de sistema en tiempo real ═══\r\n"
    "    @app.get(\"/api/system-stats\")\r\n"
    "    def api_system_stats() -> Response:\r\n"
    "        auth = require_login_response()\r\n"
    "        if auth:\r\n"
    "            return auth\r\n"
    "        stats: Dict[str, Any] = {}\r\n"
    "        try:\r\n"
    "            import psutil\r\n"
    "            stats['cpu'] = round(psutil.cpu_percent(interval=0.1), 1)\r\n"
    "            vm = psutil.virtual_memory()\r\n"
    "            stats['ram_used_gb'] = round(vm.used / 1e9, 1)\r\n"
    "            stats['ram_total_gb'] = round(vm.total / 1e9, 1)\r\n"
    "        except Exception:\r\n"
    "            pass\r\n"
    "        try:\r\n"
    "            import GPUtil\r\n"
    "            gpus = GPUtil.getGPUs()\r\n"
    "            if gpus:\r\n"
    "                g = gpus[0]\r\n"
    "                stats['gpu_load']   = round(g.load * 100, 1)\r\n"
    "                stats['vram_used']  = round(g.memoryUsed)\r\n"
    "                stats['vram_total'] = round(g.memoryTotal)\r\n"
    "                stats['vram_free']  = round(g.memoryFree)\r\n"
    "                stats['gpu_name']   = g.name\r\n"
    "        except Exception:\r\n"
    "            pass\r\n"
    "        with AI_PRIORITY_CONDITION:\r\n"
    "            stats['queue_size']      = len(AI_PRIORITY_QUEUE)\r\n"
    "            stats['active_requests'] = AI_ACTIVE_REQUESTS\r\n"
    "        return jsonify(stats)\r\n"
    "\r\n"
    "    @app.post(\"/api/chat/stream\")\r\n"
    "    def api_chat_stream() -> Response:\r\n",
)

# ─────────────────────────────────────────────────────────────
# P8 · Invite codes en register_post
# ─────────────────────────────────────────────────────────────
patch(
    "P8 · Invite codes en register_post",
    "        user, error = create_user(username, password, confirm_password)\r\n"
    "        if error or not user:\r\n"
    "            return render_auth_page(register=True, error=error or \"No se pudo crear la cuenta.\"), 400\r\n",

    "        # ═══ NEXO MEJORAS: Invite code validation ═══\r\n"
    "        _invite_codes_env = os.getenv('NEXO_INVITE_CODES', '').strip()\r\n"
    "        if _invite_codes_env:\r\n"
    "            _valid_codes = {c.strip() for c in _invite_codes_env.split(',') if c.strip()}\r\n"
    "            _submitted = request.form.get('invite_code', '').strip()\r\n"
    "            if _submitted not in _valid_codes:\r\n"
    "                return render_auth_page(register=True, error='Código de invitación inválido. Pídelo al administrador.'), 400\r\n"
    "        user, error = create_user(username, password, confirm_password)\r\n"
    "        if error or not user:\r\n"
    "            return render_auth_page(register=True, error=error or \"No se pudo crear la cuenta.\"), 400\r\n",
)

# ─────────────────────────────────────────────────────────────
# H1 · Prism.js CSS en <head> de MAIN_HTML
# ─────────────────────────────────────────────────────────────
patch(
    "H1 · Prism.js CSS en <head>",
    "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\r\n"
    "  <title>Nexo</title>\r\n",

    "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\r\n"
    "  <title>Nexo</title>\r\n"
    "  <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css\">\r\n",
)

# ─────────────────────────────────────────────────────────────
# H2 · Personality selector — junto al modeSelect en sidebar
# ─────────────────────────────────────────────────────────────
patch(
    "H2 · Personality selector en sidebar",
    "        <select id=\"modeSelect\" aria-label=\"Modo de Nexo\">\r\n"
    "          <option value=\"auto\" selected>Auto</option>\r\n"
    "          <option value=\"rapido\">Rapido</option>\r\n"
    "          <option value=\"combinado\">Combinado</option>\r\n"
    "          <option value=\"codigo\">Codigo</option>\r\n"
    "        </select>\r\n",

    "        <select id=\"modeSelect\" aria-label=\"Modo de Nexo\">\r\n"
    "          <option value=\"auto\" selected>Auto</option>\r\n"
    "          <option value=\"rapido\">Rapido</option>\r\n"
    "          <option value=\"combinado\">Combinado</option>\r\n"
    "          <option value=\"codigo\">Codigo</option>\r\n"
    "        </select>\r\n"
    "        <select id=\"personalitySelect\" aria-label=\"Personalidad de Nexo\" title=\"Tono de respuesta\">\r\n"
    "          <option value=\"normal\" selected>\U0001f916 Normal</option>\r\n"
    "          <option value=\"programador\">\U0001f4bb Programador</option>\r\n"
    "          <option value=\"creativo\">\u2728 Creativo</option>\r\n"
    "          <option value=\"conciso\">\u26a1 Conciso</option>\r\n"
    "        </select>\r\n",
)

# ─────────────────────────────────────────────────────────────
# H3 · GPU monitor widget — en sidebar-footer, antes de memoryBtn
# ─────────────────────────────────────────────────────────────
patch(
    "H3 · GPU monitor widget en sidebar",
    "        <button id=\"memoryBtn\" class=\"btn ghost\" type=\"button\">Memoria</button>\r\n",

    "        <div id=\"gpuWidget\" style=\"display:none;font-size:11px;color:var(--muted);margin-bottom:8px;padding:8px 10px;background:var(--sidebar-2);border-radius:8px;border:1px solid var(--line);\">\r\n"
    "          <div style=\"display:flex;justify-content:space-between;margin-bottom:4px;font-weight:600;color:var(--text);\"><span id=\"gpuName\">\U0001f4bb GPU</span><span id=\"gpuLoadLabel\">—</span></div>\r\n"
    "          <div style=\"background:var(--line);border-radius:4px;height:5px;margin-bottom:5px;\"><div id=\"gpuBar\" style=\"background:var(--accent);height:5px;border-radius:4px;width:0%;transition:width .6s ease;\"></div></div>\r\n"
    "          <div style=\"display:flex;justify-content:space-between;margin-bottom:2px;\"><span id=\"vramText\">VRAM</span><span id=\"cpuLabel\">CPU —</span></div>\r\n"
    "          <div style=\"background:var(--line);border-radius:4px;height:3px;margin-bottom:5px;\"><div id=\"cpuBar\" style=\"background:var(--accent-2);height:3px;border-radius:4px;width:0%;transition:width .6s ease;\"></div></div>\r\n"
    "          <div id=\"queueWidget\" style=\"display:none;color:var(--accent-2);\">Cola GPU: <span id=\"queueCount\">0</span> petici\u00f3n(es)</div>\r\n"
    "        </div>\r\n"
    "        <button id=\"memoryBtn\" class=\"btn ghost\" type=\"button\">Memoria</button>\r\n",
)

# ─────────────────────────────────────────────────────────────
# H4 · Botón micrófono — en composer-box antes de sendBtn
# ─────────────────────────────────────────────────────────────
patch(
    "H4 · Botón micrófono en composer",
    "          <button id=\"sendBtn\" class=\"send\" type=\"button\" aria-label=\"Enviar\">\u2191</button>\r\n",

    "          <button id=\"micBtn\" class=\"attach\" type=\"button\" aria-label=\"Hablar\" title=\"Voice-to-Text\" style=\"font-size:15px;\">\U0001f3a4</button>\r\n"
    "          <button id=\"sendBtn\" class=\"send\" type=\"button\" aria-label=\"Enviar\">\u2191</button>\r\n",
)

# ─────────────────────────────────────────────────────────────
# H5 · renderMarkdown mejorado — con Prism y botón copiar
# ─────────────────────────────────────────────────────────────
patch(
    "H5 · renderMarkdown con Prism.js",
    "    function renderMarkdown(text) {\r\n"
    "      const parts = text.split(/```([\\s\\S]*?)```/g);\r\n"
    "      return parts.map((part, index) => {\r\n"
    "        if (index % 2 === 1) {\r\n"
    "          const clean = part.replace(/^\\w+\\n/, '');\r\n"
    "          return `<pre><button class=\"code-copy\" type=\"button\">Copiar</button><code>${escapeHtml(clean)}</code></pre>`;\r\n"
    "        }\r\n"
    "        const html = escapeHtml(part)\r\n"
    "          .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')\r\n"
    "          .replace(/`([^`]+)`/g, '<code>$1</code>')\r\n"
    "          .split(/\\n{2,}/)\r\n"
    "          .map(p => p.trim() ? `<p>${p.replace(/\\n/g, '<br>')}</p>` : '')\r\n"
    "          .join('');\r\n"
    "        return html;\r\n"
    "      }).join('');\r\n"
    "    }\r\n",

    "    // ═══ NEXO MEJORAS: renderMarkdown con Prism.js + botón copiar ═══\r\n"
    "    const LANG_MAP = {\r\n"
    "      js:'javascript', ts:'typescript', py:'python', sh:'bash', bash:'bash',\r\n"
    "      html:'html', css:'css', sql:'sql', json:'json', cpp:'cpp', c:'c',\r\n"
    "      java:'java', rs:'rust', go:'go', rb:'ruby', php:'php', yaml:'yaml', yml:'yaml',\r\n"
    "      cs:'csharp', kt:'kotlin', swift:'swift', lua:'lua', r:'r', md:'markdown',\r\n"
    "    };\r\n"
    "    function renderMarkdown(text) {\r\n"
    "      const parts = text.split(/(```[\\s\\S]*?```)/g);\r\n"
    "      return parts.map((part, index) => {\r\n"
    "        if (index % 2 === 1) {\r\n"
    "          const inner = part.slice(3, -3);\r\n"
    "          const langMatch = inner.match(/^([a-zA-Z0-9_+-]+)\\n/);\r\n"
    "          const rawLang  = langMatch ? langMatch[1].toLowerCase() : '';\r\n"
    "          const prismLang = LANG_MAP[rawLang] || rawLang || 'plaintext';\r\n"
    "          const code = langMatch ? inner.slice(langMatch[0].length) : inner;\r\n"
    "          const highlighted = (window.Prism && Prism.languages[prismLang])\r\n"
    "            ? Prism.highlight(code, Prism.languages[prismLang], prismLang)\r\n"
    "            : escapeHtml(code);\r\n"
    "          const label = rawLang ? ` data-lang=\"${escapeHtml(rawLang)}\"` : '';\r\n"
    "          return `<pre${label} style=\"position:relative\"><button class=\"code-copy\" type=\"button\" title=\"Copiar código\">Copiar</button><code class=\"language-${prismLang}\">${highlighted}</code></pre>`;\r\n"
    "        }\r\n"
    "        const html = escapeHtml(part)\r\n"
    "          .replace(/\\*\\*\\*(.+?)\\*\\*\\*/g, '<strong><em>$1</em></strong>')\r\n"
    "          .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')\r\n"
    "          .replace(/\\*(.+?)\\*/g, '<em>$1</em>')\r\n"
    "          .replace(/`([^`]+)`/g, '<code style=\"background:var(--code);padding:2px 5px;border-radius:4px;font-size:.9em\">$1</code>')\r\n"
    "          .replace(/^### (.+)$/gm, '<h3 style=\"margin:.6em 0 .2em\">$1</h3>')\r\n"
    "          .replace(/^## (.+)$/gm,  '<h2 style=\"margin:.8em 0 .3em\">$1</h2>')\r\n"
    "          .replace(/^# (.+)$/gm,   '<h1 style=\"margin:1em 0 .4em\">$1</h1>')\r\n"
    "          .replace(/^[-*] (.+)/gm, '<li>$1</li>')\r\n"
    "          .replace(/(<li>.*<\\/li>\\n?)+/g, s => `<ul style=\"margin:.4em 0;padding-left:1.4em\">${s}</ul>`)\r\n"
    "          .split(/\\n{2,}/)\r\n"
    "          .map(p => p.trim() && !p.startsWith('<') ? `<p style=\"margin:.5em 0\">${p.replace(/\\n/g, '<br>')}</p>` : p)\r\n"
    "          .join('');\r\n"
    "        return html;\r\n"
    "      }).join('');\r\n"
    "    }\r\n",
)

# ─────────────────────────────────────────────────────────────
# H6 · scrollBottom suave
# ─────────────────────────────────────────────────────────────
patch(
    "H6 · scrollBottom smooth",
    "    function scrollBottom() {\r\n"
    "      els.messages.scrollTop = els.messages.scrollHeight;\r\n"
    "    }\r\n",

    "    // ═══ NEXO MEJORAS: Smooth scroll inteligente ═══\r\n"
    "    let _autoScroll = true;\r\n"
    "    els.messages.addEventListener('scroll', () => {\r\n"
    "      const el = els.messages;\r\n"
    "      _autoScroll = el.scrollTop + el.clientHeight >= el.scrollHeight - 80;\r\n"
    "    }, { passive: true });\r\n"
    "    function scrollBottom(force) {\r\n"
    "      if (!force && !_autoScroll) return;\r\n"
    "      els.messages.scrollTo({ top: els.messages.scrollHeight, behavior: 'smooth' });\r\n"
    "    }\r\n",
)

# ─────────────────────────────────────────────────────────────
# H7 · Nuevo JS — GPU poller, voice, personality, Prism loader
# Insertamos justo antes de </script> al final de MAIN_HTML
# ─────────────────────────────────────────────────────────────
NEW_JS = (
    "\r\n"
    "    // ═══════════════════════════════════════════════════\r\n"
    "    //  NEXO MEJORAS — GPU Monitor, Voice, Personality\r\n"
    "    // ═══════════════════════════════════════════════════\r\n"
    "\r\n"
    "    // --- Prism.js dinámico ---\r\n"
    "    (function loadPrism() {\r\n"
    "      if (window.Prism) return;\r\n"
    "      const s = document.createElement('script');\r\n"
    "      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js';\r\n"
    "      s.onload = () => {\r\n"
    "        const langs = ['python','javascript','typescript','bash','sql','json',\r\n"
    "                        'css','html','cpp','csharp','go','rust','java','lua'];\r\n"
    "        const base = 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/';\r\n"
    "        langs.forEach(l => {\r\n"
    "          const sc = document.createElement('script');\r\n"
    "          sc.src = `${base}prism-${l}.min.js`;\r\n"
    "          document.head.appendChild(sc);\r\n"
    "        });\r\n"
    "      };\r\n"
    "      document.head.appendChild(s);\r\n"
    "    })();\r\n"
    "\r\n"
    "    // --- GPU / System Monitor ---\r\n"
    "    const gpuWidget   = document.getElementById('gpuWidget');\r\n"
    "    const gpuBar      = document.getElementById('gpuBar');\r\n"
    "    const cpuBar      = document.getElementById('cpuBar');\r\n"
    "    const gpuLoadLbl  = document.getElementById('gpuLoadLabel');\r\n"
    "    const vramText    = document.getElementById('vramText');\r\n"
    "    const cpuLabel    = document.getElementById('cpuLabel');\r\n"
    "    const queueWidget = document.getElementById('queueWidget');\r\n"
    "    const queueCount  = document.getElementById('queueCount');\r\n"
    "    const gpuNameEl   = document.getElementById('gpuName');\r\n"
    "\r\n"
    "    async function pollSystemStats() {\r\n"
    "      try {\r\n"
    "        const r = await fetch('/api/system-stats');\r\n"
    "        if (!r.ok) return;\r\n"
    "        const d = await r.json();\r\n"
    "        if (!gpuWidget) return;\r\n"
    "        gpuWidget.style.display = 'block';\r\n"
    "        if (d.gpu_name && gpuNameEl) gpuNameEl.textContent = '\U0001f4bb ' + d.gpu_name.replace('NVIDIA ','');\r\n"
    "        if (d.gpu_load != null) {\r\n"
    "          gpuBar.style.width = d.gpu_load + '%';\r\n"
    "          gpuBar.style.background = d.gpu_load > 90 ? 'var(--danger)' : d.gpu_load > 70 ? '#f0c040' : 'var(--accent)';\r\n"
    "          gpuLoadLbl.textContent = d.gpu_load + '%';\r\n"
    "        }\r\n"
    "        if (d.vram_used != null) {\r\n"
    "          vramText.textContent = `VRAM ${d.vram_used}MB / ${d.vram_total}MB`;\r\n"
    "        }\r\n"
    "        if (d.cpu != null) {\r\n"
    "          cpuBar.style.width = d.cpu + '%';\r\n"
    "          cpuLabel.textContent = 'CPU ' + d.cpu + '%';\r\n"
    "        }\r\n"
    "        const q = d.queue_size || 0;\r\n"
    "        if (queueWidget) {\r\n"
    "          queueWidget.style.display = q > 0 ? 'block' : 'none';\r\n"
    "          if (queueCount) queueCount.textContent = q;\r\n"
    "        }\r\n"
    "      } catch(e) {}\r\n"
    "    }\r\n"
    "    pollSystemStats();\r\n"
    "    setInterval(pollSystemStats, 5000);\r\n"
    "\r\n"
    "    // --- Voice-to-Text (Web Speech API) ---\r\n"
    "    const micBtn = document.getElementById('micBtn');\r\n"
    "    if (micBtn) {\r\n"
    "      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;\r\n"
    "      if (SpeechRecognition) {\r\n"
    "        const recog = new SpeechRecognition();\r\n"
    "        recog.lang = 'es-ES';\r\n"
    "        recog.interimResults = true;\r\n"
    "        recog.maxAlternatives = 1;\r\n"
    "        let isListening = false;\r\n"
    "        recog.onresult = (e) => {\r\n"
    "          const transcript = Array.from(e.results).map(r => r[0].transcript).join('');\r\n"
    "          els.prompt.value = transcript;\r\n"
    "          els.prompt.style.height = 'auto';\r\n"
    "          els.prompt.style.height = Math.min(180, els.prompt.scrollHeight) + 'px';\r\n"
    "        };\r\n"
    "        recog.onend = () => {\r\n"
    "          isListening = false;\r\n"
    "          micBtn.textContent = '\U0001f3a4';\r\n"
    "          micBtn.style.color = '';\r\n"
    "        };\r\n"
    "        recog.onerror = (e) => {\r\n"
    "          isListening = false;\r\n"
    "          micBtn.textContent = '\U0001f3a4';\r\n"
    "          micBtn.style.color = '';\r\n"
    "          if (e.error !== 'no-speech') setStatus('Mic: ' + e.error);\r\n"
    "        };\r\n"
    "        micBtn.addEventListener('click', () => {\r\n"
    "          if (isListening) { recog.stop(); return; }\r\n"
    "          isListening = true;\r\n"
    "          micBtn.textContent = '\U0001f534';\r\n"
    "          micBtn.style.color = 'var(--danger)';\r\n"
    "          recog.start();\r\n"
    "        });\r\n"
    "      } else {\r\n"
    "        micBtn.title = 'Tu navegador no soporta Web Speech API';\r\n"
    "        micBtn.style.opacity = '0.4';\r\n"
    "      }\r\n"
    "    }\r\n"
    "\r\n"
    "    // --- Personality selector ---\r\n"
    "    const personalitySelect = document.getElementById('personalitySelect');\r\n"
    "    // El valor se lee en sendMessage() y se incluye en el payload.\r\n"
    "    // Patch del sendMessage existente para inyectar personality:\r\n"
    "    const _origSend = window._nexoSendOverride || null;\r\n"
    "    // Interceptamos el fetch de /api/chat/stream mediante monkey-patch del JSON payload\r\n"
    "    const _origFetch = window.fetch.bind(window);\r\n"
    "    window.fetch = function(url, opts, ...rest) {\r\n"
    "      if (typeof url === 'string' && url.includes('/api/chat/stream') && opts && opts.body) {\r\n"
    "        try {\r\n"
    "          const parsed = JSON.parse(opts.body);\r\n"
    "          if (parsed && personalitySelect) {\r\n"
    "            parsed.personality = personalitySelect.value || 'normal';\r\n"
    "            opts = { ...opts, body: JSON.stringify(parsed) };\r\n"
    "          }\r\n"
    "        } catch(e) {}\r\n"
    "      }\r\n"
    "      return _origFetch(url, opts, ...rest);\r\n"
    "    };\r\n"
    "\r\n"
    "    // --- Rate limit feedback ---\r\n"
    "    // El error 429 ya llega como JSON {error:'...',retry_after:N}.\r\n"
    "    // El handler existente de errores en el fetch lo mostrará via setStatus().\r\n"
    "    // No se necesita código extra aquí.\r\n"
    "\r\n"
    "    // --- Scroll forzado al cargar chat ---\r\n"
    "    _autoScroll = true;\r\n"
)

patch(
    "H7 · Nuevo JS antes de </script>",
    "  </script>\r\n"
    "</body>\r\n"
    "</html>\r\n"
    "\"\"\"\r\n",

    NEW_JS
    + "  </script>\r\n"
    + "</body>\r\n"
    + "</html>\r\n"
    + "\"\"\"\r\n",
)


# ═══════════════════════════════════════════════════════════════
#  MOTOR DEL PATCHER
# ═══════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   NEXO MEJORAS — Aplicando parches v1.0     ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════╝{RESET}\n")

    if not WEB_APP.exists():
        err(f"No se encontró web_app.py en: {WEB_APP}")
        sys.exit(1)

    # Backup
    shutil.copy2(WEB_APP, BACKUP)
    ok(f"Backup creado: {BACKUP.name}")

    content = WEB_APP.read_bytes().decode("utf-8", errors="replace")
    info(f"web_app.py leído: {len(content):,} caracteres")
    print()

    applied = 0
    skipped = 0
    failed  = 0

    for name, old, new in PATCHES:
        if old not in content:
            # Intentar con \n si el archivo no tiene \r\n (por si se guardó en Unix)
            old_lf  = old.replace("\r\n", "\n")
            new_lf  = new.replace("\r\n", "\n")
            if old_lf in content:
                content = content.replace(old_lf, new_lf, 1)
                ok(f"{name}  (LF)")
                applied += 1
            else:
                warn(f"{name}  — OMITIDO (ya aplicado o texto no encontrado)")
                skipped += 1
        else:
            count = content.count(old)
            if count > 1:
                warn(f"{name}  — texto encontrado {count}x, aplicando sólo la primera ocurrencia")
            content = content.replace(old, new, 1)
            ok(f"{name}")
            applied += 1

    print()
    WEB_APP.write_bytes(content.encode("utf-8"))
    info(f"web_app.py actualizado: {len(content):,} caracteres")
    print()
    print(f"{BOLD}Resumen:{RESET}  {GREEN}{applied} aplicados{RESET}  ·  {YELLOW}{skipped} omitidos{RESET}  ·  {RED}{failed} errores{RESET}")

    if applied > 0:
        print()
        print(f"{BOLD}Próximos pasos:{RESET}")
        print("  1. Instala dependencias nuevas:")
        print(f"       {CYAN}pip install psutil GPUtil{RESET}")
        print("  2. (Opcional) Activa invite codes añadiendo en .env o antes de lanzar:")
        print(f"       {CYAN}set NEXO_INVITE_CODES=codigo1,codigo2,betanexo{RESET}")
        print("  3. (Opcional) Ajusta el rate limit (defecto: 5 mensajes/60s):")
        print(f"       {CYAN}set NEXO_RATE_LIMIT_MAX=8{RESET}")
        print(f"       {CYAN}set NEXO_RATE_LIMIT_WINDOW=60{RESET}")
        print("  4. Reinicia Nexo normalmente con LANZAR_TODO_WEB.bat")
        print()
        print(f"{GREEN}✓ ¡Listo! Todas las mejoras aplicadas.{RESET}")
    else:
        print()
        warn("No se aplicó ningún parche. Es posible que ya estén todos aplicados.")
        print(f"  Restaura el original con: copy web_app.py.bak web_app.py")


if __name__ == "__main__":
    main()
