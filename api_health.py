"""
api_health.py — Watchdog de salud de APIs externas + reporte Telegram.

Detecta cuando una API se vence / se rompe / cambia de estado y avisa por
Telegram UNA sola vez (dedup por cambio de estado, no spam cada ciclo).
También expone un reporte on-demand para el comando /apihealth.

APIs vigiladas:
  - Gemini (Google AI Studio)  → key vencida / 429 spend cap / auth fail
  - Data feed (OKX/KuCoin/Bybit/Binance) → caída total del feed de velas
  - Telegram (getMe)           → token inválido
  - Etherscan / Reddit         → informativo (configurado o no)

Estado se persiste en data/api_health_state.json para comparar entre ciclos.
"""
import os
import json
import requests

STATE_FILE = "data/api_health_state.json"

# ─── Status canónicos ──────────────────────────────────────────────────────────
OK        = "OK"          # 🟢 responde bien
RATE_LIM  = "RATE_LIMIT"  # 🔴 429 / spend cap agotado
AUTH_FAIL = "AUTH_FAIL"   # 🔴 key inválida / vencida / 401-403
DOWN      = "DOWN"        # 🔴 no responde / error de red
DEGRADED  = "DEGRADED"    # ⚠️ funciona pero por fallback
SKIP      = "SKIP"        # ⚪ no configurada (opcional)

_EMOJI = {OK: "🟢", RATE_LIM: "🔴", AUTH_FAIL: "🔴", DOWN: "🔴", DEGRADED: "⚠️", SKIP: "⚪"}

# APIs cuyo cambio a estado roto dispara alerta proactiva a Telegram.
_CRITICAL = {"gemini", "data_feed"}


def _emoji(status: str) -> str:
    return _EMOJI.get(status, "❔")


# ─── Checks individuales ────────────────────────────────────────────────────────
def check_gemini() -> dict:
    """models.list via REST — barato, sin costo de tokens. Clasifica el HTTP."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return {"name": "gemini", "label": "Gemini AI", "status": AUTH_FAIL,
                "detail": "GEMINI_API_KEY no configurada"}
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key}, timeout=10)
        if r.status_code == 200:
            return {"name": "gemini", "label": "Gemini AI", "status": OK, "detail": "models.list 200"}
        if r.status_code == 429:
            return {"name": "gemini", "label": "Gemini AI", "status": RATE_LIM,
                    "detail": "429 — spend cap agotado (ai.studio/spend)"}
        if r.status_code in (400, 401, 403):
            return {"name": "gemini", "label": "Gemini AI", "status": AUTH_FAIL,
                    "detail": f"{r.status_code} — key inválida/vencida"}
        return {"name": "gemini", "label": "Gemini AI", "status": DOWN, "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"name": "gemini", "label": "Gemini AI", "status": DOWN, "detail": type(e).__name__}


def check_data_feed() -> dict:
    """Prueba cada exchange con 1 vela de BTC. Reporta cuál sirvió y cuáles cayeron."""
    from exchange_singleton import okx_spot, kucoin_spot, bybit_spot, binance_spot
    chain = [
        ("OKX",     okx_spot,     "BTC/USDT"),
        ("KuCoin",  kucoin_spot,  "BTC-USDT"),
        ("Bybit",   bybit_spot,   "BTC/USDT"),
        ("Binance", binance_spot, "BTC/USDT"),
    ]
    up, down = [], []
    for name, inst, sym in chain:
        try:
            data = inst.fetch_ohlcv(sym, timeframe="1h", limit=1)
            (up if data else down).append(name)
        except Exception as e:
            down.append(f"{name}({type(e).__name__})")

    if not up:
        return {"name": "data_feed", "label": "Data feed (velas)", "status": DOWN,
                "detail": "TODOS caídos: " + ", ".join(down)}
    # Primario = primer eslabón de la cadena (OKX). Si el primario cayó pero hay
    # backup → DEGRADED.
    primary_ok = up[0] == "OKX"
    status = OK if primary_ok else DEGRADED
    detail = f"activo: {up[0]}"
    if down:
        detail += f" · caídos: {', '.join(down)}"
    return {"name": "data_feed", "label": "Data feed (velas)", "status": status, "detail": detail}


def check_telegram() -> dict:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        return {"name": "telegram", "label": "Telegram", "status": AUTH_FAIL, "detail": "sin token"}
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        if r.status_code == 200 and r.json().get("ok"):
            return {"name": "telegram", "label": "Telegram", "status": OK,
                    "detail": "@" + r.json()["result"].get("username", "bot")}
        return {"name": "telegram", "label": "Telegram", "status": AUTH_FAIL, "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"name": "telegram", "label": "Telegram", "status": DOWN, "detail": type(e).__name__}


def check_etherscan() -> dict:
    key = os.getenv("ETHERSCAN_API_KEY")
    if not key:
        return {"name": "etherscan", "label": "Etherscan (on-chain)", "status": SKIP, "detail": "no configurada"}
    try:
        r = requests.get("https://api.etherscan.io/api",
                         params={"module": "stats", "action": "ethsupply", "apikey": key}, timeout=10)
        j = r.json()
        if str(j.get("status")) == "1" or j.get("result"):
            return {"name": "etherscan", "label": "Etherscan (on-chain)", "status": OK, "detail": "ok"}
        return {"name": "etherscan", "label": "Etherscan (on-chain)", "status": AUTH_FAIL,
                "detail": str(j.get("message") or j.get("result"))[:40]}
    except Exception as e:
        return {"name": "etherscan", "label": "Etherscan (on-chain)", "status": DOWN, "detail": type(e).__name__}


def check_reddit() -> dict:
    if not (os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")):
        return {"name": "reddit", "label": "Reddit (social)", "status": SKIP, "detail": "no configurada"}
    return {"name": "reddit", "label": "Reddit (social)", "status": OK, "detail": "credenciales presentes"}


# ─── Orquestación ───────────────────────────────────────────────────────────────
def run_all() -> list:
    """Corre todos los checks. Orden = prioridad en el reporte."""
    return [check_gemini(), check_data_feed(), check_telegram(), check_etherscan(), check_reddit()]


def format_report(results: list = None) -> str:
    """Reporte HTML para Telegram (comando /apihealth)."""
    from datetime import datetime
    if results is None:
        results = run_all()
    lines = ["🩺 <b>API HEALTH</b>", "━━━━━━━━━━━━━━━━━━"]
    broken = 0
    for r in results:
        if r["status"] in (RATE_LIM, AUTH_FAIL, DOWN):
            broken += 1
        lines.append(f"{_emoji(r['status'])} <b>{r['label']}</b> — {r['status']}")
        lines.append(f"   <i>{r['detail']}</i>")
    lines.append("━━━━━━━━━━━━━━━━━━")
    verdict = "✅ Todo operativo" if broken == 0 else f"🔴 {broken} API(s) con problema"
    lines.append(verdict)
    lines.append(f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    return "\n".join(lines)


# ─── Watchdog (alerta proactiva por cambio de estado) ───────────────────────────
def _load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ [api_health] no pude guardar estado: {e}")


def watchdog(send_telegram_fn) -> bool:
    """
    Corre los checks y compara contra el último estado guardado.
    Alerta a Telegram SOLO cuando una API crítica cambia de estado
    (sano→roto o roto→recuperado). Dedup: no repite si el estado no cambió.
    Retorna True si mandó alerta.
    """
    results = run_all()
    prev = _load_state()
    cur = {r["name"]: r["status"] for r in results}

    broke, recovered = [], []
    for r in results:
        if r["name"] not in _CRITICAL:
            continue
        old = prev.get(r["name"])
        new = r["status"]
        if old == new:
            continue
        healthy_new = new in (OK, DEGRADED)
        healthy_old = old in (OK, DEGRADED, None)
        if not healthy_new and healthy_old:
            broke.append(r)
        elif healthy_new and old is not None and not healthy_old:
            recovered.append(r)

    _save_state(cur)

    if not broke and not recovered:
        return False

    lines = ["🚨 <b>ALERTA API HEALTH</b>", "━━━━━━━━━━━━━━━━━━"]
    for r in broke:
        lines.append(f"🔴 <b>{r['label']} CAÍDA</b> — {r['status']}")
        lines.append(f"   <i>{r['detail']}</i>")
    for r in recovered:
        lines.append(f"✅ <b>{r['label']} RECUPERADA</b>")
        lines.append(f"   <i>{r['detail']}</i>")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("<i>/apihealth para ver todo</i>")
    try:
        send_telegram_fn("\n".join(lines))
        return True
    except Exception as e:
        print(f"⚠️ [api_health] no pude enviar alerta: {e}")
        return False
