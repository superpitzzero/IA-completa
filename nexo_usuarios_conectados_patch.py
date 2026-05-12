"""
╔══════════════════════════════════════════════════════════════════════╗
║  PARCHE: Usuarios conectados/desconectados en Panel Admin           ║
║  Modifica web_app.py en el lugar (in-place)                         ║
╚══════════════════════════════════════════════════════════════════════╝

Qué añade este parche:
  ✔ Rastreo de última actividad por usuario (_USER_LAST_SEEN dict global)
  ✔ Actualización automática en cada petición de chat
  ✔ Columna "Estado" en el Panel Admin con semáforo de colores:
       🟢 Verde  = activo en los últimos 5 minutos
       🟡 Naranja = activo en los últimos 30 minutos
       ⚫ Gris   = sin actividad reciente (desconectado)
  ✔ Estadística "En línea ahora" en los contadores del admin
  ✔ Refresco automático del estado cada 30 s sin recargar página

Uso:
  python nexo_usuarios_conectados_patch.py
  (hace backup automático de web_app.py → web_app.py.bak_conectados)
"""

import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

WEB_APP = Path("web_app.py")
BACKUP  = Path(f"web_app.py.bak_conectados_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

def patch(text: str) -> str:
    changes = 0

    # ──────────────────────────────────────────────────────────────────
    # 1. Añadir dict global _USER_LAST_SEEN justo después de AI_ACTIVE_REQUESTS
    # ──────────────────────────────────────────────────────────────────
    TARGET_1 = "AI_ACTIVE_REQUESTS = 0"
    INSERT_1 = (
        "\nAI_ACTIVE_REQUESTS = 0\n\n"
        "# ── Rastreo de actividad de usuarios (para panel admin) ──────────\n"
        "# user_id → timestamp Unix de la última petición de chat\n"
        "_USER_LAST_SEEN: dict = {}\n"
        "_USER_LAST_SEEN_LOCK = __import__('threading').Lock()\n"
    )
    if TARGET_1 in text and "_USER_LAST_SEEN" not in text:
        text = text.replace(TARGET_1, INSERT_1, 1)
        changes += 1
        print("  ✔ Añadido _USER_LAST_SEEN global")
    else:
        print("  ⚠ _USER_LAST_SEEN ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 2. Registrar actividad en api_chat_stream, justo después de obtener user_id
    # ──────────────────────────────────────────────────────────────────
    TARGET_2 = (
        "            user_id = str(request_user[\"id\"])\n"
        "            # ═══ NEXO MEJORAS: Rate Limiting ═══"
    )
    INSERT_2 = (
        "            user_id = str(request_user[\"id\"])\n"
        "            # ── Actualizar última actividad ──────────────────────────\n"
        "            import time as _time_mod\n"
        "            with _USER_LAST_SEEN_LOCK:\n"
        "                _USER_LAST_SEEN[user_id] = _time_mod.time()\n"
        "            # ─────────────────────────────────────────────────────────\n"
        "            # ═══ NEXO MEJORAS: Rate Limiting ═══"
    )
    if TARGET_2 in text and "_USER_LAST_SEEN[user_id]" not in text:
        text = text.replace(TARGET_2, INSERT_2, 1)
        changes += 1
        print("  ✔ Añadido rastreo de actividad en api_chat_stream")
    else:
        print("  ⚠ Rastreo ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 3. Incluir last_seen y online en admin_list_users
    # ──────────────────────────────────────────────────────────────────
    TARGET_3 = (
        '            "registration_order": i + 1,\n'
        "        })\n"
        "    return result"
    )
    INSERT_3 = (
        '            "registration_order": i + 1,\n'
        "        })\n"
        "    # Enriquecer con estado de conexión\n"
        "    import time as _t\n"
        "    now = _t.time()\n"
        "    with _USER_LAST_SEEN_LOCK:\n"
        "        snap = dict(_USER_LAST_SEEN)\n"
        "    for entry in result:\n"
        "        uid = entry.get('id', '')\n"
        "        last = snap.get(uid)\n"
        "        if last:\n"
        "            elapsed = now - last\n"
        "            entry['last_seen'] = int(last)\n"
        "            if elapsed < 300:    # < 5 min\n"
        "                entry['online_status'] = 'online'\n"
        "            elif elapsed < 1800: # < 30 min\n"
        "                entry['online_status'] = 'recent'\n"
        "            else:\n"
        "                entry['online_status'] = 'offline'\n"
        "        else:\n"
        "            entry['last_seen'] = None\n"
        "            entry['online_status'] = 'offline'\n"
        "    return result"
    )
    if TARGET_3 in text and "online_status" not in text:
        text = text.replace(TARGET_3, INSERT_3, 1)
        changes += 1
        print("  ✔ Añadido last_seen y online_status en admin_list_users")
    else:
        print("  ⚠ online_status ya existe o no se encontró el ancla en admin_list_users")

    # ──────────────────────────────────────────────────────────────────
    # 4. Añadir columna "Estado" en la cabecera de la tabla del admin
    # ──────────────────────────────────────────────────────────────────
    TARGET_4 = "          <th>Cambiar plan</th>\n        </tr>"
    INSERT_4 = "          <th>Estado</th>\n          <th>Cambiar plan</th>\n        </tr>"
    if TARGET_4 in text and "<th>Estado</th>" not in text:
        text = text.replace(TARGET_4, INSERT_4, 1)
        changes += 1
        print("  ✔ Añadida columna Estado en cabecera de tabla")
    else:
        print("  ⚠ Columna Estado ya existe o no se encontró la cabecera")

    # ──────────────────────────────────────────────────────────────────
    # 5. Añadir estadística "En línea ahora" en el statsBar
    # ──────────────────────────────────────────────────────────────────
    TARGET_5 = (
        '      <div class="stat"><div class="stat-val" id="statTotal">—</div>'
        '<div class="stat-lbl">Usuarios totales</div></div>'
    )
    INSERT_5 = (
        '      <div class="stat"><div class="stat-val" id="statTotal">—</div>'
        '<div class="stat-lbl">Usuarios totales</div></div>\n'
        '      <div class="stat"><div class="stat-val" style="color:#19c37d" id="statOnline">—</div>'
        '<div class="stat-lbl">🟢 En línea ahora</div></div>'
    )
    if TARGET_5 in text and 'statOnline' not in text:
        text = text.replace(TARGET_5, INSERT_5, 1)
        changes += 1
        print("  ✔ Añadida estadística 'En línea ahora'")
    else:
        print("  ⚠ Estadística online ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 6. Añadir CSS para los indicadores de estado
    # ──────────────────────────────────────────────────────────────────
    TARGET_6 = "    .date-cell { color: var(--muted); font-size: 11px; }"
    INSERT_6 = (
        "    .date-cell { color: var(--muted); font-size: 11px; }\n"
        "    .status-dot { display:inline-block; width:10px; height:10px; border-radius:50%; "
        "margin-right:5px; flex-shrink:0; }\n"
        "    .status-online  { background:#19c37d; box-shadow:0 0 6px #19c37d88; }\n"
        "    .status-recent  { background:#f0c040; }\n"
        "    .status-offline { background:#555; }\n"
        "    .status-cell { display:flex; align-items:center; gap:4px; font-size:12px; "
        "color:var(--muted); white-space:nowrap; }\n"
    )
    if TARGET_6 in text and ".status-dot" not in text:
        text = text.replace(TARGET_6, INSERT_6, 1)
        changes += 1
        print("  ✔ Añadido CSS para indicadores de estado")
    else:
        print("  ⚠ CSS de estado ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 7. Actualizar el JS de renderizado de filas para incluir la celda Estado
    # ──────────────────────────────────────────────────────────────────
    # Buscamos la parte del innerHTML del tr en el JS del admin
    TARGET_7 = (
        "          <td class=\\"date-cell\\">${fmtDate(u.created_at)}</td>\n"
        "          <td style=\\"display:flex;gap:8px;align-items:center\\">"
    )
    INSERT_7 = (
        "          <td class=\\"date-cell\\">${fmtDate(u.created_at)}</td>\n"
        "          <td class=\\"status-cell\\">${statusDot(u.online_status, u.last_seen)}</td>\n"
        "          <td style=\\"display:flex;gap:8px;align-items:center\\">"
    )
    if TARGET_7 in text and "statusDot" not in text:
        text = text.replace(TARGET_7, INSERT_7, 1)
        changes += 1
        print("  ✔ Añadida celda Estado en filas de la tabla")
    else:
        print("  ⚠ Celda Estado ya existe o no se encontró el ancla JS")

    # ──────────────────────────────────────────────────────────────────
    # 8. Añadir función statusDot y actualizar loadUsers para estadística online
    # ──────────────────────────────────────────────────────────────────
    TARGET_8 = "    function planBadge(key) {"
    INSERT_8 = r"""    function statusDot(status, lastSeen) {
      const cls = {online:'status-online', recent:'status-recent', offline:'status-offline'}[status] || 'status-offline';
      let label = 'Sin actividad';
      if (lastSeen) {
        const secs = Math.floor(Date.now()/1000 - lastSeen);
        if (secs < 60) label = 'Ahora';
        else if (secs < 3600) label = `Hace ${Math.floor(secs/60)}m`;
        else label = `Hace ${Math.floor(secs/3600)}h`;
      }
      return `<span class="status-dot ${cls}"></span>${label}`;
    }

    function planBadge(key) {"""
    if TARGET_8 in text and "function statusDot" not in text:
        text = text.replace(TARGET_8, INSERT_8, 1)
        changes += 1
        print("  ✔ Añadida función statusDot en JS admin")
    else:
        print("  ⚠ statusDot ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 9. Actualizar statOnline en loadUsers
    # ──────────────────────────────────────────────────────────────────
    TARGET_9 = (
        "      document.getElementById('statTotal').textContent = users.length;\n"
        "      document.getElementById('statGold').textContent"
    )
    INSERT_9 = (
        "      document.getElementById('statTotal').textContent = users.length;\n"
        "      const onlineCount = users.filter(u => u.online_status === 'online').length;\n"
        "      const onlineEl = document.getElementById('statOnline');\n"
        "      if (onlineEl) onlineEl.textContent = onlineCount;\n"
        "      document.getElementById('statGold').textContent"
    )
    if TARGET_9 in text and "onlineCount" not in text:
        text = text.replace(TARGET_9, INSERT_9, 1)
        changes += 1
        print("  ✔ Actualizado contador de usuarios online")
    else:
        print("  ⚠ Contador online ya existe o no se encontró el ancla")

    # ──────────────────────────────────────────────────────────────────
    # 10. Auto-refresco del estado cada 30 s (al final del script admin)
    # ──────────────────────────────────────────────────────────────────
    TARGET_10 = "    loadUsers();"
    INSERT_10 = (
        "    loadUsers();\n"
        "    // Auto-refresco del estado de conexión cada 30 s\n"
        "    setInterval(loadUsers, 30000);\n"
    )
    if TARGET_10 in text and "setInterval(loadUsers" not in text:
        # Reemplaza solo la primera aparición para no duplicar
        text = text.replace(TARGET_10, INSERT_10, 1)
        changes += 1
        print("  ✔ Añadido auto-refresco cada 30 s")
    else:
        print("  ⚠ Auto-refresco ya existe o no se encontró el ancla")

    print(f"\n  Total de cambios aplicados: {changes}/10")
    return text


def main():
    if not WEB_APP.exists():
        print(f"❌ No se encontró {WEB_APP}. Ejecuta este script desde la carpeta del proyecto.")
        sys.exit(1)

    print(f"📂 Leyendo {WEB_APP} …")
    original = WEB_APP.read_text(encoding="utf-8")

    print(f"💾 Creando backup → {BACKUP}")
    shutil.copy2(WEB_APP, BACKUP)

    print("\n🔧 Aplicando parches …\n")
    patched = patch(original)

    if patched == original:
        print("\n⚠️  No se realizaron cambios (puede que el parche ya estuviera aplicado).")
    else:
        WEB_APP.write_text(patched, encoding="utf-8")
        print(f"\n✅ {WEB_APP} actualizado correctamente.")
        print(f"   Backup guardado en: {BACKUP}")

    print("\n──────────────────────────────────────────────")
    print("Reinicia la web para que los cambios surtan efecto:")
    print("  python launch_web.py")
    print("──────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
