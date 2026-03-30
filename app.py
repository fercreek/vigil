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
    for s in ["SOL/USDT", "BTC/USDT", "TAO/USDT"]:
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

    SYMBOLS = ["SOL/USDT", "BTC/USDT", "TAO/USDT"]
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
@app.route('/api/backtest/monthly')
def get_backtest_monthly():
    """Agrega el historial de backtests por mes para la vista mensual."""
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

if __name__ == '__main__':
    print("🚀 Dashboard de Scalping UI iniciado en http://localhost:5001")
    app.run(debug=True, port=5001)
