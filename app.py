from flask import Flask, render_template, jsonify
import tracker
import analysis_science

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    full_won, partial_won, lost, total = tracker.get_win_rate()
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

if __name__ == '__main__':
    print("🚀 Dashboard de Scalping UI iniciado en http://localhost:5001")
    app.run(debug=True, port=5001)
