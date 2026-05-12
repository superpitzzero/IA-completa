"""
NEXO Stats Addon
================
Modulo de estadisticas avanzadas para web_app.py.

Como activar (solo 3 lineas en web_app.py dentro de create_app()):

    from stats_addon import init_stats_addon, track_message
    init_stats_addon(app, is_admin_user_fn=is_admin_user, public_plan_fn=public_plan_for_user)

Y luego, dentro de api_chat_stream() despues de obtener user_id y mode,
añadir UNA linea:

    track_message(user_id=user_id, username=request_user.get('username',''),
                  plan=user_plan, mode=mode, message=user_message)

Listo. El boton "📊 Stats" aparece automaticamente en topbar para admins,
y la pagina /admin/stats muestra todo.
"""
from __future__ import annotations
import json, os, time, threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from flask import Flask, jsonify, Response, session, redirect

# ---------- Persistencia ligera (JSON) ------------------------------------
_STATS_FILE = Path(os.getenv("NEXO_STATS_FILE", "web_data/stats.json"))
_LOCK = threading.Lock()
_STATE = {
    "messages": [],        # [{ts, user_id, username, plan, mode, tokens_in}]
    "totals": {"by_user": {}, "by_mode": {}, "by_plan": {}, "all": 0},
    "latency_samples": [], # [{ts, ms, mode}]
}
_RECENT_ACTIVITY: deque = deque(maxlen=2000)  # actividad reciente para "usuarios activos"

def _load() -> None:
    if _STATS_FILE.exists():
        try:
            with _LOCK:
                data = json.loads(_STATS_FILE.read_text(encoding="utf-8"))
                _STATE.update({k: data.get(k, _STATE[k]) for k in _STATE})
        except Exception as e:
            print(f"[STATS] No se pudo cargar {_STATS_FILE}: {e}")

def _save() -> None:
    try:
        _STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            _STATS_FILE.write_text(json.dumps(_STATE, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[STATS] No se pudo guardar: {e}")

# ---------- API publica del modulo ----------------------------------------
def track_message(user_id: str, username: str, plan: str, mode: str, message: str = "", latency_ms: int = 0) -> None:
    """Registra un mensaje. Llamar tras procesar /api/chat/stream."""
    now = time.time()
    rec = {"ts": now, "user_id": str(user_id), "username": username or "?",
           "plan": plan or "gratis", "mode": mode or "rapido",
           "tokens_in": max(1, len(message.split()))}
    with _LOCK:
        _STATE["messages"].append(rec)
        # Mantener solo ultimos 30 dias para no crecer infinito
        cutoff = now - 30 * 86400
        _STATE["messages"] = [m for m in _STATE["messages"] if m["ts"] >= cutoff]
        t = _STATE["totals"]
        t["all"] = t.get("all", 0) + 1
        t["by_user"][rec["username"]] = t["by_user"].get(rec["username"], 0) + 1
        t["by_mode"][rec["mode"]] = t["by_mode"].get(rec["mode"], 0) + 1
        t["by_plan"][rec["plan"]] = t["by_plan"].get(rec["plan"], 0) + 1
        if latency_ms > 0:
            _STATE["latency_samples"].append({"ts": now, "ms": int(latency_ms), "mode": rec["mode"]})
            _STATE["latency_samples"] = _STATE["latency_samples"][-2000:]
        _RECENT_ACTIVITY.append((now, rec["username"]))
    if _STATE["totals"]["all"] % 5 == 0:
        threading.Thread(target=_save, daemon=True).start()


def _compute_stats() -> dict:
    now = time.time()
    day_ago = now - 86400
    week_ago = now - 7 * 86400
    month_ago = now - 30 * 86400
    five_min = now - 300
    with _LOCK:
        msgs = list(_STATE["messages"])
        lats = list(_STATE["latency_samples"])
        totals = dict(_STATE["totals"])
        recent_users = {u for ts, u in _RECENT_ACTIVITY if ts >= five_min}

    def _cnt(after): return sum(1 for m in msgs if m["ts"] >= after)
    by_user_today = defaultdict(int)
    by_mode_today = defaultdict(int)
    for m in msgs:
        if m["ts"] >= day_ago:
            by_user_today[m["username"]] += 1
            by_mode_today[m["mode"]] += 1

    top5 = sorted(totals.get("by_user", {}).items(), key=lambda x: -x[1])[:5]
    top5_today = sorted(by_user_today.items(), key=lambda x: -x[1])[:5]

    # latencias por modo
    lat_by_mode: dict = defaultdict(list)
    for s in lats[-500:]:
        lat_by_mode[s["mode"]].append(s["ms"])
    avg_lat = {m: int(sum(v)/len(v)) for m, v in lat_by_mode.items() if v}

    return {
        "total_messages": totals.get("all", 0),
        "messages_today": _cnt(day_ago),
        "messages_week":  _cnt(week_ago),
        "messages_month": _cnt(month_ago),
        "active_users_5min": len(recent_users),
        "active_users_list": sorted(recent_users),
        "by_mode": dict(totals.get("by_mode", {})),
        "by_mode_today": dict(by_mode_today),
        "by_plan": dict(totals.get("by_plan", {})),
        "top5_all_time": [{"user": u, "msgs": n} for u, n in top5],
        "top5_today":    [{"user": u, "msgs": n} for u, n in top5_today],
        "avg_latency_ms_by_mode": avg_lat,
        "tokens_estimated": sum(m.get("tokens_in", 0) for m in msgs),
    }

# ---------- HTML pagina /admin/stats --------------------------------------
_STATS_PAGE_HTML = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>NEXO · Stats</title>
<style>
  :root{--bg:#0b0e14;--card:#141925;--bd:#222a3a;--fg:#e6e9ef;--mut:#8892a6;--ac:#7dd3fc;--gd:#f0c040;--dn:#ef4444}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
  header{padding:18px 24px;border-bottom:1px solid var(--bd);display:flex;justify-content:space-between;align-items:center;gap:12px}
  header h1{margin:0;font-size:20px;letter-spacing:.5px}
  header a{color:var(--ac);text-decoration:none;font-size:13px}
  main{padding:24px;max-width:1300px;margin:0 auto}
  .grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px}
  .kpi{font-size:30px;font-weight:700;color:var(--ac);margin:6px 0}
  .lbl{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--bd)}
  th{color:var(--mut);font-weight:500;text-transform:uppercase;font-size:11px;letter-spacing:.06em}
  .bar{height:8px;background:#1e2434;border-radius:4px;overflow:hidden;margin-top:4px}
  .bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--ac),var(--gd))}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
  @media(max-width:900px){.row{grid-template-columns:1fr}}
  .muted{color:var(--mut)} .gd{color:var(--gd)} .dn{color:var(--dn)}
  .badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;background:#1e2434;border:1px solid var(--bd);margin-right:4px}
  .refresh{padding:6px 12px;background:transparent;color:var(--ac);border:1px solid var(--ac);border-radius:6px;cursor:pointer;font-size:12px}
  .refresh:hover{background:rgba(125,211,252,.1)}
</style></head><body>
<header>
  <div><h1>📊 NEXO · Panel de Estadísticas</h1>
    <div class="muted" style="font-size:12px">Actualizado <span id="upd">…</span></div></div>
  <div style="display:flex;gap:10px">
    <button class="refresh" onclick="load()">🔄 Refrescar</button>
    <a href="/admin">← Panel Admin</a>
    <a href="/">🏠 Inicio</a>
  </div>
</header>
<main>
  <div class="grid" id="kpis"></div>
  <div class="row">
    <div class="card"><div class="lbl">Top 5 usuarios — TOTAL</div><table id="topAll"></table></div>
    <div class="card"><div class="lbl">Top 5 usuarios — HOY</div><table id="topToday"></table></div>
  </div>
  <div class="row">
    <div class="card"><div class="lbl">Mensajes por modo (total)</div><div id="modeAll"></div></div>
    <div class="card"><div class="lbl">Mensajes por plan</div><div id="planAll"></div></div>
  </div>
  <div class="row">
    <div class="card"><div class="lbl">Latencia media por modo</div><div id="lats"></div></div>
    <div class="card"><div class="lbl">Sistema (CPU / GPU / VRAM / cola)</div><div id="sys"></div></div>
  </div>
  <div class="card" style="margin-top:16px"><div class="lbl">Usuarios activos últimos 5 min</div><div id="actUsers" style="margin-top:8px"></div></div>
</main>
<script>
async function load(){
  try{
    const [s,sy] = await Promise.all([fetch('/api/admin/full-stats').then(r=>r.json()), fetch('/api/system-stats').then(r=>r.json()).catch(()=>({}))]);
    document.getElementById('upd').textContent = new Date().toLocaleTimeString();
    // KPIs
    const k = document.getElementById('kpis');
    const cards = [
      ['Mensajes hoy', s.messages_today, '#7dd3fc'],
      ['Mensajes semana', s.messages_week, '#a78bfa'],
      ['Mensajes mes', s.messages_month, '#f0c040'],
      ['Mensajes TOTAL', s.total_messages, '#22c55e'],
      ['Usuarios activos (5min)', s.active_users_5min, '#ef4444'],
      ['Tokens estimados (30d)', s.tokens_estimated.toLocaleString(), '#7dd3fc'],
    ];
    k.innerHTML = cards.map(([l,v,c])=>`<div class="card"><div class="lbl">${l}</div><div class="kpi" style="color:${c}">${v}</div></div>`).join('');
    // Tops
    const fmtTable = (arr)=>`<thead><tr><th>#</th><th>Usuario</th><th style="text-align:right">Mensajes</th></tr></thead><tbody>${arr.length?arr.map((r,i)=>`<tr><td class="muted">${i+1}</td><td>${r.user}</td><td style="text-align:right" class="gd">${r.msgs}</td></tr>`).join(''):'<tr><td colspan=3 class="muted">Sin datos aún</td></tr>'}</tbody>`;
    document.getElementById('topAll').innerHTML = fmtTable(s.top5_all_time);
    document.getElementById('topToday').innerHTML = fmtTable(s.top5_today);
    // Modos
    const fmtBars = (obj)=>{ const tot=Object.values(obj).reduce((a,b)=>a+b,0)||1; return Object.entries(obj).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between"><span>${k}</span><span class="muted">${v} (${Math.round(v*100/tot)}%)</span></div><div class="bar"><i style="width:${v*100/tot}%"></i></div></div>`).join('')||'<div class="muted">Sin datos</div>'; };
    document.getElementById('modeAll').innerHTML = fmtBars(s.by_mode);
    document.getElementById('planAll').innerHTML = fmtBars(s.by_plan);
    // Latencias
    const lats = s.avg_latency_ms_by_mode;
    document.getElementById('lats').innerHTML = Object.keys(lats).length ? Object.entries(lats).map(([m,ms])=>`<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--bd)"><span class="badge">${m}</span><span class="${ms>10000?'dn':ms>5000?'gd':''}">${(ms/1000).toFixed(1)} s</span></div>`).join('') : '<div class="muted">Aún sin muestras</div>';
    // Sistema
    document.getElementById('sys').innerHTML = `
      <div>💻 ${sy.gpu_name||'GPU'}</div>
      <div style="margin-top:6px">GPU: <b class="gd">${sy.gpu_load??'?'}%</b> · VRAM: <b>${sy.vram_used??'?'} / ${sy.vram_total??'?'} MB</b></div>
      <div>CPU: <b>${sy.cpu??'?'}%</b> · RAM: <b>${sy.ram_used_gb??'?'} / ${sy.ram_total_gb??'?'} GB</b></div>
      <div style="margin-top:6px">🔄 Cola IA: <b class="${(sy.queue_size||0)>0?'gd':''}">${sy.queue_size??0}</b> · Activas: <b>${sy.active_requests??0}</b></div>`;
    // Activos
    document.getElementById('actUsers').innerHTML = (s.active_users_list||[]).length ? s.active_users_list.map(u=>`<span class="badge" style="color:var(--ac);border-color:var(--ac)">${u}</span>`).join(' ') : '<span class="muted">Nadie ha enviado mensajes en los últimos 5 minutos</span>';
  }catch(e){ console.error(e); document.getElementById('upd').textContent = 'error'; }
}
load(); setInterval(load, 8000);
</script></body></html>"""

# ---------- Registro Flask ------------------------------------------------
def init_stats_addon(app: Flask, is_admin_user_fn=None, public_plan_fn=None) -> None:
    """Registra endpoints y pagina /admin/stats."""
    _load()

    def _admin_only():
        username = session.get("username", "") if session else ""
        if not username or (is_admin_user_fn and not is_admin_user_fn(username)):
            return False
        return True

    @app.get("/admin/stats")
    def stats_page():
        if not _admin_only():
            return redirect("/login")
        return Response(_STATS_PAGE_HTML, mimetype="text/html")

    @app.get("/api/admin/full-stats")
    def api_full_stats():
        if not _admin_only():
            return jsonify({"error": "forbidden"}), 403
        return jsonify(_compute_stats())

    print("[STATS] Addon activo: /admin/stats y /api/admin/full-stats")
