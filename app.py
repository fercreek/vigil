from flask import Flask, render_template, jsonify, request
import tracker
import scalp_alert_bot
import ai_budget
from datetime import datetime, timedelta
import time

try:
    import analysis_science
    _HAS_ANALYSIS = True
except ImportError:
    analysis_science = None
    _HAS_ANALYSIS = False
    print("[app.py] AVISO: analysis_science no disponible — backtesting deshabilitado")

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', active_tab='live', preload_date=None)

@app.route('/reports')
def reports():
    return render_template('index.html', active_tab='reports', preload_date=None)

@app.route('/monthly')
def monthly():
    return render_template('index.html', active_tab='monthly', preload_date=None)

@app.route('/analysis')
def analysis():
    return render_template('index.html', active_tab='analysis', preload_date=None)

@app.route('/alerts')
def alerts():
    return render_template('index.html', active_tab='alerts', preload_date=None)

@app.route('/budget')
def budget():
    return render_template('index.html', active_tab='budget', preload_date=None)

@app.route('/flow')
def flow():
    return render_template('index.html', active_tab='flow', preload_date=None)

@app.route('/report/<date_str>')
def report_day(date_str):
    """URL directa para un reporte, ej: /report/2026-03-27"""
    return render_template('index.html', active_tab='reports', preload_date=date_str)

@app.route('/api/stats')
def get_stats():
    try:
        version = request.args.get('version')
        full_won, partial_won, lost, total = tracker.get_win_rate(version)
        win_rate = round(((full_won + partial_won) / total) * 100, 1) if total > 0 else 0
        return jsonify({
            "full_won": full_won, 
            "partial_won": partial_won, 
            "lost": lost, 
            "total": total, 
            "win_rate": win_rate,
            "last_updated": int(time.time()),
            "last_updated_iso": datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({"error": str(e), "full_won": 0, "partial_won": 0, "lost": 0, "total": 0, "win_rate": 0}), 500

@app.route('/api/trades')
def get_trades():
    try:
        return jsonify(tracker.get_all_trades())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics')
def get_metrics():
    """Metricas avanzadas: Sharpe, Sortino, MaxDD, SQN, Calmar, PF."""
    try:
        import metrics
        trades = tracker.get_recent_outcomes(n=200)
        report = metrics.generate_full_report(trades)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/macro')
def get_macro():
    try:
        data = scalp_alert_bot.GLOBAL_CACHE["macro_metrics"].copy()
        data["last_updated"] = scalp_alert_bot.GLOBAL_CACHE["last_update"].get("macro_metrics", 0)
        data["last_updated_iso"] = datetime.fromtimestamp(
            data["last_updated"]
        ).strftime('%H:%M:%S') if data["last_updated"] else "N/A"
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/indicators')
def get_all_indicators():
    """Retorna los indicadores actuales (incluyendo POC) de la caché del bot."""
    try:
        data = scalp_alert_bot.GLOBAL_CACHE["indicators"].copy()
        # Intentar obtener el timestamp más reciente de los indicadores
        last_upd = 0
        if scalp_alert_bot.GLOBAL_CACHE["last_update"]["indicators"]:
            last_upd = max(scalp_alert_bot.GLOBAL_CACHE["last_update"]["indicators"].values())
        
        return jsonify({
            "indicators": data,
            "last_updated": last_upd,
            "last_updated_iso": datetime.fromtimestamp(last_upd).strftime('%H:%M:%S') if last_upd else "N/A"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis')
def get_analysis():
    if not _HAS_ANALYSIS:
        return jsonify({"error": "Módulo analysis_science no disponible"}), 503
    results = []
    for s in ["ZEC/USDT", "TAO/USDT", "BTC/USDT"]:
        try:
            res = analysis_science.scientific_analysis(s)
            if res:
                results.append(res)
        except Exception as e:
            results.append({"symbol": s, "error": str(e)})
    return jsonify(results)

@app.route('/api/backtest/days')
def get_backtest_days():
    """Lista días con reportes guardados en la BD."""
    try:
        return jsonify(tracker.get_backtest_days())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backtest/compare')
def get_backtest_compare():
    try:
        date_str = request.args.get('date')
        force = request.args.get('force', 'false').lower() == 'true'

        if not date_str:
            date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        SYMBOLS = ["ZEC/USDT", "TAO/USDT", "BTC/USDT"]
        VERSIONS = ["V1-TECH", "V2-AI"]

        # Verificar si ya existe en DB (y no se fuerza recálculo)
        existing_v1 = tracker.get_backtest_session(date_str, version="V1-TECH")
        existing_v2 = tracker.get_backtest_session(date_str, version="V2-AI")

        if existing_v1 and existing_v2 and not force:
            # Cargar de la BD
            return jsonify({
                "date": date_str,
                "source": "database",
                "V1-TECH": existing_v1,
                "V2-AI": existing_v2
            })

        if not _HAS_ANALYSIS:
            return jsonify({"error": "Módulo analysis_science no disponible"}), 503

        # Generar simulación y guardar
        all_trades = {"V1-TECH": [], "V2-AI": []}
        for v in VERSIONS:
            for s in SYMBOLS:
                trades = analysis_science.run_detailed_backtest(s, target_date_str=date_str, version=v)
                all_trades[v].extend(trades)
            # Persistir en BD con cálculo de balance $1000
            tracker.save_backtest_session(date_str, v, all_trades[v])

        # Recargar desde BD para devolver con balance calculado
        return jsonify({
            "date": date_str,
            "source": "simulation",
            "V1-TECH": tracker.get_backtest_session(date_str, version="V1-TECH"),
            "V2-AI": tracker.get_backtest_session(date_str, version="V2-AI")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/backtest/monthly')
def get_backtest_monthly():
    """Agrega el historial de backtests por mes para la vista mensual."""
    try:
        all_days = tracker.get_backtest_days()
        if not all_days:
            return jsonify([])
        
        # Obtener todos los días únicos con datos
        unique_dates = sorted(set(d['date'] for d in all_days), reverse=True)
        
        monthly_data = {}
        
        for date_str in unique_dates:
            month_key = date_str[:7]  # 'YYYY-MM'
            if month_key not in monthly_data:
                monthly_data[month_key] = {'V1-TECH': {'days':[]}, 'V2-AI': {'days':[]}}
            
            for version in ['V1-TECH', 'V2-AI']:
                trades = tracker.get_backtest_session(date_str, version=version)
                if not trades:
                    continue
                
                won = sum(1 for t in trades if t['result'] == 'WIN_FULL')
                lost = sum(1 for t in trades if t['result'] == 'LOST')
                open_eod = sum(1 for t in trades if t['result'] == 'OPEN_EOD')
                total_pnl = round(sum(t['pnl_usd'] or 0 for t in trades), 2)
                final_bal = trades[-1]['balance_after'] if trades else 1000
                win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else 0
                
                monthly_data[month_key][version]['days'].append({
                    'date': date_str,
                    'trades': len(trades),
                    'won': won,
                    'lost': lost,
                    'open_eod': open_eod,
                    'win_rate': win_rate,
                    'pnl': total_pnl,
                    'balance': final_bal
                })
        
        # Calcular totales por mes
        result = []
        for month_key in sorted(monthly_data.keys(), reverse=True):
            month_obj = {'month': month_key, 'V1-TECH': None, 'V2-AI': None}
            for version in ['V1-TECH', 'V2-AI']:
                days = monthly_data[month_key][version]['days']
                if not days:
                    continue
                total_pnl = round(sum(d['pnl'] for d in days), 2)
                total_won = sum(d['won'] for d in days)
                total_lost = sum(d['lost'] for d in days)
                total_trades = sum(d['trades'] for d in days)
                win_rate = round(total_won / (total_won + total_lost) * 100, 1) if (total_won + total_lost) > 0 else 0
                
                month_obj[version] = {
                    'days_count': len(days),
                    'total_trades': total_trades,
                    'total_won': total_won,
                    'total_lost': total_lost,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'days': sorted(days, key=lambda x: x['date'])
                }
            result.append(month_obj)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts/map')
def get_alerts_map():
    """
    Catálogo completo de tipos de alerta con condiciones y win rate histórico.
    Permite a agentes/usuarios elegir qué estrategias seguir según su perfil.
    """
    try:
        # Catálogo estático — condiciones de cada tipo de alerta
        catalog = {
            "v1_long": {
                "name": "V1-TECH LONG",
                "version": "V1-TECH",
                "direction": "LONG",
                "risk_profile": "CONSERVADOR",
                "conditions": [
                    "Macro BULL (EMA200 1H + 4H ambas alcistas)",
                    "Precio > EMA200 (1H)",
                    "RSI <= 42 (ZEC: 48) en vela 1H",
                    "RSI subiendo (vs vela anterior)",
                    "Precio cerca Banda Bollinger Inferior (< 1.5% margen)",
                    "Confluence Score >= 4/6"
                ],
                "filters_tested": {
                    "Williams %R <= -85": "80% WR en BTC (N=5), 66.7% en TAO (N=6)",
                    "BB Width >= 3%": "72.7% WR en BTC (N=11)",
                    "ADX >= 20": "65.5% WR en ZEC (N=29)"
                },
                "backtest_wr": 27.1,
                "backtest_n": 49,
                "notes": "Señal principal. Poca frecuencia (84 candles/año BTC) pero alta selectividad."
            },
            "v1_short": {
                "name": "V1-TECH SHORT",
                "version": "V1-TECH",
                "direction": "SHORT",
                "risk_profile": "DESACTIVADO",
                "conditions": ["DESACTIVADO — bot en modo LONG FOCUS"],
                "filters_tested": {},
                "backtest_wr": None,
                "backtest_n": 0,
                "notes": "Desactivado por diseño en la versión actual."
            },
            "v2_ai_long": {
                "name": "V2-AI LONG (Gemini Confirm)",
                "version": "V2-AI",
                "direction": "LONG",
                "risk_profile": "MODERADO",
                "conditions": [
                    "Todas las condiciones de V1-TECH LONG",
                    "Gemini AI confirma decision=CONFIRM",
                    "Análisis de 4 personas: Bull, Bear, Quant, Macro"
                ],
                "filters_tested": {},
                "backtest_wr": None,
                "backtest_n": 0,
                "notes": "Capa AI sobre V1. Mayor latencia. Requiere cuota de Gemini."
            },
            "v2_ai_consensus": {
                "name": "V2-AI CONSENSUS (Dual Agent)",
                "version": "V2-AI",
                "direction": "LONG/SHORT",
                "risk_profile": "AGRESIVO",
                "conditions": [
                    "RSI <= 40",
                    "Dos agentes Gemini independientes coinciden en dirección",
                    "Filtro de tendencia EMA200"
                ],
                "filters_tested": {},
                "backtest_wr": None,
                "backtest_n": 0,
                "notes": "Alta frecuencia de disparo. Solo recomendado con VIX bajo y macro BULL."
            },
            "v2_ai_short": {
                "name": "V2-AI SHORT",
                "version": "V2-AI",
                "direction": "SHORT",
                "risk_profile": "DESACTIVADO",
                "conditions": ["DESACTIVADO — modo LONG FOCUS"],
                "filters_tested": {},
                "backtest_wr": None,
                "backtest_n": 0,
                "notes": "Desactivado por diseño."
            },
            "v3_reversal": {
                "name": "V3 Reversal Intradía",
                "version": "V1-TECH",
                "direction": "LONG",
                "risk_profile": "AGRESIVO",
                "conditions": [
                    "Fase LONG activa",
                    "Precio < EMA200 (opera contra tendencia mayor)",
                    "RSI <= 35 (oversold extremo)",
                    "Cerca Banda Bollinger Inferior",
                    "Confluence Score >= 3/6"
                ],
                "filters_tested": {},
                "backtest_wr": None,
                "backtest_n": 0,
                "notes": "Opera contra tendencia. Alta volatilidad. Solo para scalping agresivo con SL ajustado."
            }
        }

        # Stats históricas desde la DB
        live_stats = {s["alert_type"]: s for s in tracker.get_alert_stats()}

        # Fusionar catálogo con datos reales
        result = []
        for alert_type, info in catalog.items():
            db_data = live_stats.get(alert_type, {})
            result.append({
                **info,
                "live_total": db_data.get("total", 0),
                "live_wins": db_data.get("wins", 0),
                "live_losses": db_data.get("losses", 0),
                "live_win_rate": db_data.get("win_rate"),
                "live_by_symbol": db_data.get("by_symbol", {})
            })

        return jsonify({
            "alert_types": result,
            "summary": {
                "active_strategies": [a["name"] for a in result if a["risk_profile"] != "DESACTIVADO"],
                "disabled_strategies": [a["name"] for a in result if a["risk_profile"] == "DESACTIVADO"],
                "recommended_conservative": ["v1_long"],
                "recommended_moderate": ["v1_long", "v2_ai_long"],
                "recommended_aggressive": ["v1_long", "v2_ai_long", "v2_ai_consensus", "v3_reversal"]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/ai_budget')
def get_ai_budget():
    """Retorna el consumo de APIs de IA y estado del presupuesto mensual."""
    try:
        month  = request.args.get('month')   # opcional: YYYY-MM
        monthly = ai_budget.get_monthly_cost(month)
        daily   = ai_budget.get_daily_decisions()
        recent  = ai_budget.get_recent_calls(limit=15)
        return jsonify({
            **monthly,
            "daily_decisions":     daily,
            "max_daily_decisions": ai_budget.MAX_DAILY_DECISIONS,
            "daily_remaining":     max(0, ai_budget.MAX_DAILY_DECISIONS - daily),
            "recent_calls":        recent,
            "last_updated_iso":    datetime.now().strftime('%H:%M:%S'),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/shadow_intel')
def get_shadow_intel():
    """Retorna mensajes reales de monitoreo neural (Shadow Sentinel)."""
    try:
        # Intentar obtener de la caché del bot o devolver vacíos.
        msgs = scalp_alert_bot.GLOBAL_CACHE.get("shadow_messages", [])
        return jsonify(msgs)
    except Exception as e:
        return jsonify([])

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """
    Recibe alertas del Pine Script de TradingView como señal adicional.

    Payload JSON esperado:
    {
        "symbol": "ZEC",        # o BTC, TAO, HBAR, DOGE
        "direction": "LONG",    # LONG | SHORT | ESPERAR
        "rsi": 27.3,
        "price": 270.52,
        "strategy": "Zenith V17",
        "confidence": 0.9       # opcional, default 0.8
    }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        symbol    = str(data.get("symbol", "")).upper().strip()
        direction = str(data.get("direction", "")).upper().strip()
        rsi       = float(data.get("rsi", 50))
        price     = float(data.get("price", 0))
        strategy  = str(data.get("strategy", "TradingView"))
        confidence = float(data.get("confidence", 0.8))

        if not symbol or direction not in ("LONG", "SHORT", "ESPERAR"):
            return jsonify({"ok": False, "error": "symbol o direction inválido"}), 400

        import signal_coordinator as _sc
        import alert_manager as _am
        import scalp_alert_bot as _bot

        ts = datetime.now().strftime("%H:%M")
        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⏳"
        msg = (
            f"📡 <b>TRADINGVIEW WEBHOOK [{ts}]</b>\n"
            f"<code>{symbol} @ ${price:,.2f} | RSI {rsi:.1f}</code>\n"
            f"━━━━━━━━━━━━━\n"
            f"{emoji} <b>SEÑAL: {direction}</b> — {strategy}\n"
            f"━━━━━━━━━━━━━\n"
            f"<i>Señal recibida del Pine Script. Evaluando confluencia...</i>"
        )

        _sc.submit("TRADINGVIEW", symbol, direction, confidence, msg)
        sent = _sc.resolve_and_send(symbol, _am.send_telegram)

        print(f"📡 [TradingView Webhook] {symbol} {direction} @ ${price} | sent={sent}")
        return jsonify({"ok": True, "symbol": symbol, "direction": direction, "sent": bool(sent)})

    except Exception as e:
        print(f"❌ [TradingView Webhook] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("🚀 Dashboard de Scalping UI iniciado en http://localhost:5001")
    app.run(debug=True, port=5001)
