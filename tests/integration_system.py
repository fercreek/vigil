"""
integration_system.py — Test de pulso Zenith Trading Suite (API actual).

Verifica 3 secciones críticas contra el sistema real:
  1. Conectividad + Precios + Indicadores
  2. Signal Logger (roundtrip log → read)
  3. AI Budget tracking (log_ai_call → get_monthly_cost)

Uso:
    venv/bin/python tests/integration_system.py

Salida: PASS/FAIL por sección. Exit 0 = todo OK.
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

_PASS = "\033[92mPASS\033[0m"
_FAIL = "\033[91mFAIL\033[0m"
_fails = []


def section(title, fn):
    print(f"\n[{title}]")
    try:
        fn()
    except Exception as e:
        print(f"  [{_FAIL}] excepción: {e}")
        _fails.append(title)


# ── Sección 1: Conectividad, Precios, Indicadores ────────────────────────────

def _test_prices_indicators():
    from scalp_alert_bot import get_prices
    import indicators

    prices = get_prices()
    btc = prices.get("BTC", 0)
    eth = prices.get("ETH", 0)
    assert btc > 0, f"BTC = {btc} (esperado > 0)"
    assert eth > 0, f"ETH = {eth} (esperado > 0)"
    print(f"  [{_PASS}] Precios: BTC=${btc:,.0f} ETH=${eth:,.0f}")

    rsi_btc = indicators.get_rsi("BTC", "15m")
    assert 0 < rsi_btc < 100, f"RSI BTC = {rsi_btc} fuera de rango"
    print(f"  [{_PASS}] RSI BTC 15m = {rsi_btc:.1f}")

    rsi_zec = indicators.get_rsi("ZEC", "15m")
    assert 0 < rsi_zec < 100, f"RSI ZEC = {rsi_zec} fuera de rango"
    print(f"  [{_PASS}] RSI ZEC 15m = {rsi_zec:.1f}")


# ── Sección 2: Signal Logger roundtrip ───────────────────────────────────────

def _test_signal_logger():
    import signal_logger

    # Escribir entry de test
    signal_logger.log_signal(
        "_TEST", "INTEGRATION", "SENT", "pulse check",
        price=1.0, rsi=50.0
    )

    # Leer de vuelta
    rows = signal_logger.get_recent_signals(n=10, symbol="_TEST")
    assert len(rows) >= 1, "log_signal() escribió pero get_recent_signals() no lo encuentra"
    last = rows[-1]
    assert last["symbol"] == "_TEST"
    assert last["decision"] == "SENT"
    assert last["strategy"] == "INTEGRATION"
    print(f"  [{_PASS}] signal_logger roundtrip OK — {last['ts'][:16]}")

    # Summary
    summary = signal_logger.get_signal_summary(hours=1)
    assert "totals" in summary
    print(f"  [{_PASS}] get_signal_summary() OK — totals: {summary['totals']}")


# ── Sección 3: AI Budget tracking ────────────────────────────────────────────

def _test_ai_budget():
    import ai_budget

    # Verificar rates no son cero
    rates_gemini = ai_budget.COST_PER_TOKEN.get("gemini-2.5-flash", {})
    assert rates_gemini.get("in", 0) > 0, "gemini-2.5-flash rate 'in' = 0.0 (bug)"
    assert rates_gemini.get("out", 0) > 0, "gemini-2.5-flash rate 'out' = 0.0 (bug)"
    print(f"  [{_PASS}] Gemini rates: in=${rates_gemini['in']*1e6:.2f}/M out=${rates_gemini['out']*1e6:.2f}/M")

    # Log una llamada de test
    cost = ai_budget.log_ai_call(
        provider="gemini",
        model="gemini-2.5-flash",
        call_type="integration_test",
        tokens_in=1000,
        tokens_out=100,
        symbol="_TEST",
    )
    assert cost > 0, f"log_ai_call() retornó cost={cost} (esperado > 0)"
    print(f"  [{_PASS}] log_ai_call() costo calculado: ${cost:.6f}")

    # Verificar aparece en monthly
    monthly = ai_budget.get_monthly_cost()
    assert monthly["calls"] >= 1, "get_monthly_cost() calls = 0 tras log_ai_call()"
    print(f"  [{_PASS}] get_monthly_cost() OK — calls={monthly['calls']} total=${monthly['total_usd']:.4f}")


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    print("\n🧪 ZENITH INTEGRATION TEST\n")
    section("1. Conectividad + Precios + Indicadores", _test_prices_indicators)
    section("2. Signal Logger roundtrip",              _test_signal_logger)
    section("3. AI Budget tracking",                   _test_ai_budget)

    print()
    if _fails:
        print(f"❌ {len(_fails)} sección(es) FAIL: {', '.join(_fails)}")
        sys.exit(1)
    else:
        print("✅ 3/3 secciones PASS — sistema operacional.")
        sys.exit(0)


if __name__ == "__main__":
    main()
