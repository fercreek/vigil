from flask import Flask, render_template, jsonify, request
import tracker
import analysis_science
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', preload_date=None)

@app.route('/report/<date_str>')
def report_day(date_str):
    """URL directa para un reporte, ej: /report/2026-03-27"""
    return render_template('index.html', preload_date=date_str)

@app.route('/api/stats')
def get_stats():
    version = request.args.get('version')
    full_won, partial_won, lost, total = tracker.get_win_rate(version)
    win_rate = round(((full_won + partial_won) / total) * 100, 1) if total > 0 else 0
    return jsonify({"full_won": full_won, "partial_won": partial_won, "lost": lost, "total": total, "win_rate": win_rate})

@app.route('/api/trades')
def get_trades():
    return jsonify(tracker.get_all_trades())

@app.route('/api/analysis')
def get_analysis():
    results = []
    for s in ["ETH/USDT", "BTC/USDT", "TAO/USDT"]:
        res = analysis_science.scientific_analysis(s)
        if res:
            results.append(res)
    return jsonify(results)

@app.route('/api/backtest/days')
def get_backtest_days():
    """Lista días con reportes guardados en la BD."""
    return jsonify(tracker.get_backtest_days())

@app.route('/api/backtest/compare')
def get_backtest_compare():
    date_str = request.args.get('date')
    force = request.args.get('force', 'false').lower() == 'true'

    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    SYMBOLS = ["ETH/USDT", "BTC/USDT", "TAO/USDT"]
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

if __name__ == '__main__':
    print("🚀 Dashboard de Scalping UI iniciado en http://localhost:5001")
    app.run(debug=True, port=5001)
