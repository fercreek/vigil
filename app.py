from flask import Flask, render_template, jsonify, request
import tracker
import analysis_science
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    version = request.args.get('version') # Opcional: ?version=V1-TECH
    full_won, partial_won, lost, total = tracker.get_win_rate(version)
    win_rate = 0
    if total > 0:
        win_rate = ((full_won + partial_won) / total) * 100
        
    return jsonify({
        "full_won": full_won,
        "partial_won": partial_won,
        "lost": lost,
        "total": total,
        "win_rate": round(win_rate, 1)
    })

@app.route('/api/trades')
def get_trades():
    trades = tracker.get_all_trades()
    return jsonify(trades)

@app.route('/api/analysis')
def get_analysis():
    results = []
    for s in ["ETH/USDT", "BTC/USDT", "TAO/USDT"]:
        res = analysis_science.scientific_analysis(s)
        if res:
            results.append(res)
    return jsonify(results)

@app.route('/api/backtest/compare')
def get_backtest_compare():
    today_weekday = datetime.now().weekday()
    days_to_friday = (today_weekday - 4) % 7
    if days_to_friday == 0: days_to_friday = 7
    
    results = {"V1-TECH": {}, "V2-AI": {}}
    for s in ["ETH/USDT", "BTC/USDT", "TAO/USDT"]:
        results["V1-TECH"][s] = analysis_science.run_detailed_backtest(s, days_ago=days_to_friday, version="V1-TECH")
        results["V2-AI"][s] = analysis_science.run_detailed_backtest(s, days_ago=days_to_friday, version="V2-AI")
    return jsonify(results)

if __name__ == '__main__':
    print("🚀 Dashboard de Scalping UI iniciado en http://localhost:5001")
    app.run(debug=True, port=5001)
