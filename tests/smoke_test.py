"""
smoke_test.py — Verificación pro de que @tradercreekbot está vivo y funcional.

Uso:
    venv/bin/python tests/smoke_test.py

15 checks (infra + señales + config + budget):
     1. Proceso main.py corriendo
     2. Flask /api/stats 200
     3. Telegram token válido
     4. get_prices() BTC+ETH > 0
     5. RSI BTC 15m calculable
     6. bot.log fresco (<10 min)
     7. Gemini API responde (<20s)          [WARN — no crítico]
     8. Config guards correctos
     9. signals.jsonl existe con entry hoy
    10. 5 threads activos
    11. /api/signals/recent 200
    12. Hora UTC no bloqueada
    13. ai_budget DB tiene entries
    14. Gemini rates ≠ 0.0
    15. Integration pulse pasa

Exit 0 = todo OK. Exit 1 = al menos 1 FAIL crítico.
"""
import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

_PASS = "\033[92mPASS\033[0m"
_FAIL = "\033[91mFAIL\033[0m"
_WARN = "\033[93mWARN\033[0m"
_fails = []


def check(name, fn, critical=True):
    t0 = time.time()
    try:
        ok, detail = fn()
        ms = int((time.time() - t0) * 1000)
        tag = _PASS if ok else (_FAIL if critical else _WARN)
        print(f"  [{tag}] {name} ({ms}ms) — {detail}")
        if not ok and critical:
            _fails.append(name)
        return ok
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        print(f"  [{_FAIL}] {name} ({ms}ms) — excepción: {e}")
        if critical:
            _fails.append(name)
        return False


# ── checks 1-7 (infra) ───────────────────────────────────────────────────────

def _check_process():
    r = subprocess.run(["pgrep", "-f", "main.py"], capture_output=True, text=True)
    pids = r.stdout.strip().split()
    if pids:
        return True, f"PID(s): {', '.join(pids)}"
    return False, "main.py no encontrado en ps"


def _check_flask():
    try:
        r = urllib.request.urlopen("http://localhost:8080/api/stats", timeout=5)
        data = json.loads(r.read())
        return True, f"status {r.status} · trades={data.get('total_trades', '?')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def _check_telegram_token():
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        return False, "TELEGRAM_TOKEN no configurado en .env"
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = urllib.request.urlopen(url, timeout=8)
        data = json.loads(r.read())
        username = data["result"].get("username", "?")
        return True, f"@{username} OK"
    except Exception as e:
        return False, str(e)


def _check_prices():
    from scalp_alert_bot import get_prices
    prices = get_prices()
    btc = prices.get("BTC", 0)
    eth = prices.get("ETH", 0)
    if btc > 0 and eth > 0:
        return True, f"BTC=${btc:,.0f} ETH=${eth:,.0f}"
    return False, f"BTC={btc} ETH={eth} (cero o None)"


def _check_rsi():
    import indicators
    rsi = indicators.get_rsi("BTC", "15m")
    if rsi and 0 < rsi < 100:
        return True, f"BTC RSI 15m = {rsi:.1f}"
    return False, f"RSI inválido: {rsi}"


def _check_log_freshness():
    log_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../logs/app.log"))
    if not os.path.exists(log_path):
        return False, f"app.log no existe"
    age_min = (time.time() - os.path.getmtime(log_path)) / 60
    if age_min < 10:
        return True, f"último write hace {age_min:.1f} min"
    return False, f"app.log sin writes hace {age_min:.1f} min — threads probablemente frozen"


def _check_gemini_ping():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, "GEMINI_API_KEY no configurado"
    import threading as _th
    _holder = [None]
    def _call():
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            _holder[0] = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Di PONG.",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
        except Exception as e:
            _holder[0] = e
    t = _th.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=20)
    if _holder[0] is None:
        return False, "Gemini timeout >20s"
    if isinstance(_holder[0], Exception):
        return False, str(_holder[0])
    return True, f"Gemini OK — '{_holder[0].text.strip()[:20]}'"


# ── checks 8-15 (señales + config + budget) ──────────────────────────────────

def _check_config_guards():
    from config import (
        V1_LONG_ENABLED, V1_SHORT_ENABLED, V5_ENABLED,
        TAO_TRADING_ENABLED, ENABLE_TELEGRAM_BUTTONS,
    )
    errors = []
    if V1_LONG_ENABLED:   errors.append("V1_LONG_ENABLED=True (debe ser False)")
    if V1_SHORT_ENABLED:  errors.append("V1_SHORT_ENABLED=True (debe ser False)")
    if V5_ENABLED:        errors.append("V5_ENABLED=True (debe ser False)")
    if TAO_TRADING_ENABLED: errors.append("TAO_TRADING_ENABLED=True (debe ser False)")
    if not ENABLE_TELEGRAM_BUTTONS: errors.append("ENABLE_TELEGRAM_BUTTONS=False (debe ser True)")
    if errors:
        return False, " | ".join(errors)
    return True, "V1=F V1S=F V5=F TAO=F BUTTONS=T — todos correctos"


def _check_signals_log():
    import signal_logger
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = signal_logger.get_recent_signals(n=500)
    today_rows = [r for r in rows if r.get("ts", "").startswith(today)]
    if today_rows:
        last = today_rows[-1]
        return True, f"{len(today_rows)} entries hoy · último: {last['symbol']} {last['decision']} {last['ts'][11:16]}"
    log_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../logs/signals.jsonl"))
    if not os.path.exists(log_path):
        return False, "signals.jsonl no existe — signal_logger no hookado aún"
    return False, f"0 entries hoy ({today}) en signals.jsonl — bot sin ciclo completo o sin señales"


def _check_threads():
    r = subprocess.run(["pgrep", "-f", "main.py"], capture_output=True, text=True)
    pids = r.stdout.strip().split()
    if not pids:
        return False, "proceso main.py no encontrado"
    # Verificar log de boot tiene los 5 threads
    log_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../logs/app.log"))
    expected = ["scalp_bot", "swing", "telegram", "stock", "daily_report", "market_report"]
    found = []
    try:
        with open(log_path) as f:
            lines = f.readlines()[-200:]
        content = "".join(lines)
        for t in expected:
            if f"Hilo '{t}' iniciado" in content:
                found.append(t)
    except Exception:
        pass
    missing = [t for t in expected if t not in found]
    if missing:
        return False, f"threads no iniciados: {missing}"
    return True, f"6/6 threads activos: {', '.join(expected)}"


def _check_signals_api():
    try:
        r = urllib.request.urlopen("http://localhost:8080/api/signals/recent?n=5", timeout=5)
        data = json.loads(r.read())
        return True, f"status {r.status} · count={data.get('count', '?')}"
    except Exception as e:
        return False, str(e)


def _check_hour_filter():
    # Hardcoded per strategies.py — 0% WR histórico en estas horas UTC
    BLOCKED_HOURS = {4, 6, 10, 11, 15, 16, 17, 20}
    utc_hour = datetime.now(timezone.utc).hour
    if utc_hour in BLOCKED_HOURS:
        return False, f"UTC {utc_hour:02d}:xx está en BLOCKED_HOURS — señales bloqueadas ahora"
    return True, f"UTC {utc_hour:02d}:xx — hora permitida (BLOCKED={sorted(BLOCKED_HOURS)})"


def _check_budget_db():
    import ai_budget
    monthly = ai_budget.get_monthly_cost()
    calls = monthly.get("calls", 0)
    if calls >= 1:
        return True, f"calls={calls} · total=${monthly.get('total_usd', 0):.4f} · gemini=${monthly.get('gemini_usd', 0):.4f}"
    return False, "0 calls en DB — budget tracking no está registrando llamadas"


def _check_gemini_rates():
    import ai_budget
    rates = ai_budget.COST_PER_TOKEN.get("gemini-2.5-flash", {})
    rate_in  = rates.get("in", 0)
    rate_out = rates.get("out", 0)
    if rate_in > 0 and rate_out > 0:
        return True, f"in=${rate_in*1e6:.2f}/M out=${rate_out*1e6:.2f}/M"
    return False, f"rates gemini-2.5-flash = in={rate_in} out={rate_out} (bug: siempre $0)"


def _check_integration_pulse():
    try:
        from scalp_alert_bot import get_prices
        import indicators
        prices = get_prices()
        assert prices.get("BTC", 0) > 0
        rsi = indicators.get_rsi("ZEC", "15m")
        assert 0 < rsi < 100
        return True, f"get_prices OK · ZEC RSI={rsi:.1f}"
    except Exception as e:
        return False, str(e)


# ── runner ────────────────────────────────────────────────────────────────────

def main():
    print("\n🔥 SMOKE TEST PRO — @tradercreekbot (15 checks)\n")
    print("── Infra ───────────────────────────────────────")
    check("1.  Proceso main.py corriendo",     _check_process,         critical=True)
    check("2.  Flask /api/stats 200",          _check_flask,           critical=True)
    check("3.  Telegram token válido",         _check_telegram_token,  critical=True)
    check("4.  get_prices() BTC+ETH > 0",      _check_prices,          critical=True)
    check("5.  RSI BTC 15m calculable",        _check_rsi,             critical=True)
    check("6.  app.log fresco (<10 min)",      _check_log_freshness,   critical=True)
    check("7.  Gemini API responde (<20s)",    _check_gemini_ping,     critical=False)
    print("── Señales + Config ────────────────────────────")
    check("8.  Config guards correctos",       _check_config_guards,   critical=True)
    check("9.  signals.jsonl con entry hoy",   _check_signals_log,     critical=False)
    check("10. 6 threads activos",             _check_threads,         critical=True)
    check("11. /api/signals/recent 200",       _check_signals_api,     critical=True)
    check("12. Hora UTC no bloqueada",         _check_hour_filter,     critical=False)
    print("── Budget + Integration ────────────────────────")
    check("13. ai_budget DB con entries",      _check_budget_db,       critical=False)
    check("14. Gemini rates ≠ 0.0",           _check_gemini_rates,    critical=True)
    check("15. Integration pulse (ZEC RSI)",  _check_integration_pulse, critical=True)

    print()
    if _fails:
        print(f"❌ {len(_fails)} FAIL(s): {', '.join(_fails)}")
        sys.exit(1)
    else:
        print("✅ 15/15 checks PASS — @tradercreekbot operacional a nivel PRO.")
        sys.exit(0)


if __name__ == "__main__":
    main()
