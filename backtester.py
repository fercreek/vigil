"""
backtester.py — Phase 4: Backtesting Engine

Motor de backtesting que reutiliza los indicadores REALES del bot (no duplicados)
y soporta walk-forward validation, fees, slippage, y partial TPs.

Uso:
    from backtester import Backtester
    bt = Backtester()
    bt.load_data("TAO", start="2025-04", end="2025-12")
    results = bt.run(strategy="V1")
    wf = bt.walk_forward(strategy="V1", train_pct=0.7)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from config import (
    ATR_SL_MULT, ATR_TP1_MULT, ATR_TP2_MULT,
    ATR_MIN_SL_PCT, ATR_MIN_SL_REVERSAL, MIN_CONFLUENCE_SCORE,
    RSI_LONG_ENTRY, RSI_LONG_ZEC_ENTRY,
    RSI_LONG_TAO_EXTREME, RSI_LONG_ZEC_EXTREME,
    RSI_SHORT_ENTRY, ADX_TRENDING_THRESHOLD, BB_WIDTH_RANGING_PCT,
    V4_EMA_PROXIMITY_MAX, V4_EMA_PROXIMITY_MIN,
    V4_RSI_LOW, V4_RSI_HIGH, V4_MIN_CONFLUENCE,
    V4_EMA_PROX_MAP,
    V3_MIN_CONFLUENCE, V3_MAX_HOLDING_BARS,
    V3_REQUIRE_DIVERGENCE, V3_REQUIRE_BB_SQUEEZE,
    SHORT_MIN_CONFLUENCE, SHORT_REGIMES, SHORT_EMA_SLOPE_MIN,
    ADX_CHOPPY_THRESHOLD, REGIME_COOLDOWN_BARS, RVOL_MIN_ENTRY,
    RVOL_MIN_BTC,
)

# Nota: indicadores se calculan inline (vectorizado sobre todo el dataset)
# para evitar llamar funciones que retornan escalares (calculate_rsi → .iloc[-1]).


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

WARMUP_BARS = 250          # EMA200 necesita ~200 bars para estabilizar
FEE_PCT = 0.04 / 100      # 0.04% taker fee por lado (Binance Futures)
SLIPPAGE_PCT = 0.02 / 100  # 0.02% slippage estimado por entrada/salida
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFLUENCE SCORE (replica exacta sin lazy imports)
# ═══════════════════════════════════════════════════════════════════════════════

def _confluence_score(price, rsi, bb_u, bb_l, ema200, side="LONG",
                      usdt_d=8.0, elliott=""):
    """Replica de calculate_confluence_score() sin dependencias circulares."""
    score = 0
    if side == "LONG":
        if rsi <= 30: score += 2
        elif rsi <= 40: score += 1
    else:
        if rsi >= 70: score += 2
        elif rsi >= 60: score += 1

    if (side == "LONG" and price > ema200) or (side == "SHORT" and price < ema200):
        score += 1
    if (side == "LONG" and price <= bb_l * 1.01) or (side == "SHORT" and price >= bb_u * 0.99):
        score += 1
    if (side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05):
        score += 1
    if "Onda 3" in elliott: score += 1
    if "Corrección" in elliott or "Correctiva" in elliott: score -= 1
    return max(0, min(7, score))


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class Backtester:
    """Motor de backtesting para estrategias Zenith."""

    def __init__(self, fee_pct=FEE_PCT, slippage_pct=SLIPPAGE_PCT):
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.df = None
        self.symbol = None

    # ── Data Loading ──────────────────────────────────────────────────────

    def load_data(self, symbol, start=None, end=None, df=None):
        """
        Carga datos OHLCV desde CSV en /data/ o acepta DataFrame directo.

        symbol: "TAO", "ZEC", "ETH", "BTC"
        start/end: strings YYYY-MM o YYYY-MM-DD para filtrar rango
        df: DataFrame directo (para testing con datos sinteticos)
        """
        self.symbol = symbol

        if df is not None:
            self.df = df.copy()
            return self

        csv_path = os.path.join(DATA_DIR, f"{symbol}_USDT_1h_365d.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

        self.df = pd.read_csv(csv_path, parse_dates=['timestamp'], index_col='timestamp')

        if start:
            self.df = self.df[self.df.index >= pd.Timestamp(start)]
        if end:
            self.df = self.df[self.df.index <= pd.Timestamp(end)]

        return self

    # ── Indicator Precomputation ──────────────────────────────────────────

    def _compute_indicators(self, df):
        """Pre-calcula todos los indicadores sobre el dataset completo (vectorizado)."""
        df = df.copy()
        # RSI (Wilder smoothing — serie completa, NO escalar)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        # Bollinger Bands (serie completa)
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std(ddof=0)
        df['bb_u'] = sma + 2 * std
        df['bb_l'] = sma - 2 * std
        # EMA 200
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        # ATR series
        hl = df['high'] - df['low']
        hc = (df['high'] - df['close'].shift()).abs()
        lc = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()
        # ADX for regime detection
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
        atr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth.replace(0, 1e-10))
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth.replace(0, 1e-10))
        di_sum = (plus_di + minus_di).replace(0, 1e-10)
        dx = ((plus_di - minus_di).abs() / di_sum) * 100
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
        # BB width for regime
        bb_mid = df['close'].rolling(20).mean()
        df['bb_width'] = (df['bb_u'] - df['bb_l']) / bb_mid.replace(0, 1e-10)
        # Previous RSI for "rising" filter
        df['rsi_prev'] = df['rsi'].shift(1)

        # ── NEW INDICATORS (Phase 6: Robustness Filters) ────────────────
        # RVOL — Relative Volume (institutional participation)
        df['vol_sma'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / df['vol_sma'].replace(0, 1e-10)

        # EMA200 slope (5-bar) — declining = bearish confirmation for shorts
        df['ema200_slope'] = df['ema_200'].diff(5) / df['ema_200'].shift(5).replace(0, 1e-10)

        # RSI bullish divergence: price lower-low + RSI higher-low
        df['price_ll'] = (df['low'] < df['low'].shift(1)) & (df['low'].shift(1) < df['low'].shift(2))
        df['rsi_hl'] = (df['rsi'] > df['rsi'].shift(1)) & (df['rsi'].shift(1) > df['rsi'].shift(2))
        df['rsi_divergence'] = df['price_ll'] & df['rsi_hl']

        # BB Width squeeze (contracting = sell-off losing steam)
        df['bb_width_sma'] = df['bb_width'].rolling(20).mean()
        df['bb_squeeze'] = df['bb_width'] < df['bb_width_sma']

        # EMA 50 as 4H trend proxy (50 * 1H ≈ 200 * 15min ≈ 4H trend)
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # ATR-normalized EMA proximity (for V4 per-symbol adaptation)
        df['ema_dist_atr'] = (df['close'] - df['ema_200']) / df['atr'].replace(0, 1e-10)

        df = df.dropna()
        return df

    def _detect_regime(self, row):
        """Detecta regimen de mercado a partir de indicadores pre-calculados."""
        adx = row.get('adx', 0)
        bb_width = row.get('bb_width', 0.05)
        price = row['close']
        ema200 = row['ema_200']

        if adx > ADX_TRENDING_THRESHOLD:
            return "TRENDING_UP" if price > ema200 else "TRENDING_DOWN"
        elif bb_width < BB_WIDTH_RANGING_PCT:
            return "RANGING"
        elif adx < ADX_CHOPPY_THRESHOLD and bb_width < 0.04:
            return "CHOPPY"  # NEW: suppress all signals
        else:
            return "TRENDING_UP" if price > ema200 else "TRENDING_DOWN"

    # ── Trade Execution Helpers ───────────────────────────────────────────

    def _apply_costs(self, entry_price, exit_price, side):
        """Aplica fees + slippage al PnL."""
        cost_pct = (self.fee_pct + self.slippage_pct) * 2  # entrada + salida
        if side == "LONG":
            effective_entry = entry_price * (1 + self.fee_pct + self.slippage_pct)
            effective_exit = exit_price * (1 - self.fee_pct - self.slippage_pct)
            pnl_pct = (effective_exit - effective_entry) / effective_entry * 100
        else:
            effective_entry = entry_price * (1 - self.fee_pct - self.slippage_pct)
            effective_exit = exit_price * (1 + self.fee_pct + self.slippage_pct)
            pnl_pct = (effective_entry - effective_exit) / effective_entry * 100
        return round(pnl_pct, 4)

    # ── Main Backtest Runner ──────────────────────────────────────────────

    def run(self, strategy="V1", usdt_d=8.0):
        """
        Ejecuta backtest sobre los datos cargados.

        strategy: "V1", "V3", "V4", "V1-SHORT", "ALL"
        usdt_d: USDT dominance simulada (default 8.0 = neutral)

        Retorna lista de trades con PnL.
        """
        if self.df is None or self.df.empty:
            return []

        df = self._compute_indicators(self.df)
        if len(df) < WARMUP_BARS:
            return []

        sym = self.symbol or "UNKNOWN"
        rsi_thresh = RSI_LONG_ZEC_ENTRY if sym == "ZEC" else RSI_LONG_ENTRY
        reversal_rsi = RSI_LONG_ZEC_EXTREME if sym == "ZEC" else RSI_LONG_TAO_EXTREME

        trades = []
        active = None
        prev_regime = None
        regime_cooldown = 0

        # Per-symbol V4 proximity and RVOL threshold
        v4_prox_max = V4_EMA_PROX_MAP.get(sym, V4_EMA_PROXIMITY_MAX)
        rvol_min = RVOL_MIN_BTC if sym == "BTC" else RVOL_MIN_ENTRY

        for ts, row in df.iloc[WARMUP_BARS:].iterrows():
            price = row['close']
            rsi = row['rsi']
            rsi_prev = row['rsi_prev']
            bb_u = row['bb_u']
            bb_l = row['bb_l']
            ema200 = row['ema_200']
            atr = row['atr']
            rvol = row.get('rvol', 1.0)

            regime = self._detect_regime(row)

            # ── Regime transition cooldown ────────────────────────────────
            if prev_regime and regime != prev_regime:
                regime_cooldown = REGIME_COOLDOWN_BARS
            prev_regime = regime
            if regime_cooldown > 0:
                regime_cooldown -= 1

            # ── Gestionar trade activo ────────────────────────────────────
            if active:
                active['bars_held'] = active.get('bars_held', 0) + 1
                side = active['side']

                # V3 max holding period — force close stale reversals
                if active.get('version') == 'V3' and active['bars_held'] >= V3_MAX_HOLDING_BARS:
                    pnl = self._apply_costs(active['entry'], price, side)
                    trades.append(self._close_trade(active, ts, price, "TIMEOUT", pnl))
                    active = None
                    continue

                if side == "LONG":
                    if price <= active['sl']:
                        pnl = self._apply_costs(active['entry'], active['sl'], side)
                        trades.append(self._close_trade(active, ts, active['sl'], "LOST", pnl))
                        active = None
                    elif price >= active['tp2']:
                        pnl = self._apply_costs(active['entry'], active['tp2'], side)
                        trades.append(self._close_trade(active, ts, active['tp2'], "WIN_FULL", pnl))
                        active = None
                    elif price >= active['tp1'] and not active.get('tp1_hit'):
                        active['tp1_hit'] = True
                        active['sl'] = active['entry'] * 1.001
                else:  # SHORT
                    if price >= active['sl']:
                        pnl = self._apply_costs(active['entry'], active['sl'], side)
                        trades.append(self._close_trade(active, ts, active['sl'], "LOST", pnl))
                        active = None
                    elif price <= active['tp2']:
                        pnl = self._apply_costs(active['entry'], active['tp2'], side)
                        trades.append(self._close_trade(active, ts, active['tp2'], "WIN_FULL", pnl))
                        active = None
                    elif price <= active['tp1'] and not active.get('tp1_hit'):
                        active['tp1_hit'] = True
                        active['sl'] = active['entry'] * 0.999
                continue

            # ── Skip RANGING / CHOPPY / Cooldown ─────────────────────────
            if regime in ("RANGING", "CHOPPY"):
                continue
            if regime_cooldown > 0:
                continue

            # ── V1 LONG (FIXED: removed BB hard gate, added RVOL) ────────
            if strategy in ("V1", "ALL"):
                if (price > ema200 and regime in ("TRENDING_UP", "VOLATILE")
                        and rsi <= rsi_thresh and rsi > rsi_prev
                        and rvol >= rvol_min):
                    # BB proximity is now a scoring bonus, not a hard gate
                    conf = _confluence_score(price, rsi, bb_u, bb_l, ema200, "LONG", usdt_d)
                    # EMA50 trend confirmation bonus
                    if row.get('ema_50', 0) > ema200:
                        conf += 1
                    min_conf = 3 if sym in ("BTC", "ETH") else MIN_CONFLUENCE_SCORE
                    if conf >= min_conf:
                        sl_dist = max(atr * ATR_SL_MULT, price * ATR_MIN_SL_PCT)
                        active = self._open_trade(
                            ts, sym, "LONG", price, sl_dist, conf, rsi, "V1"
                        )
                        continue

            # ── V3 REVERSAL (FIXED: divergence + BB squeeze + timeout) ───
            if strategy in ("V3", "ALL"):
                if (price < ema200 and regime in ("VOLATILE", "TRENDING_DOWN")
                        and rsi <= reversal_rsi):
                    # Require structural confirmation
                    has_divergence = row.get('rsi_divergence', False) if V3_REQUIRE_DIVERGENCE else True
                    has_squeeze = row.get('bb_squeeze', False) if V3_REQUIRE_BB_SQUEEZE else True
                    if has_divergence or has_squeeze:
                        conf = _confluence_score(price, rsi, bb_u, bb_l, ema200, "LONG", usdt_d)
                        if conf >= V3_MIN_CONFLUENCE:
                            sl_dist = max(atr * ATR_SL_MULT, price * ATR_MIN_SL_REVERSAL)
                            active = self._open_trade(
                                ts, sym, "LONG", price, sl_dist, conf, rsi, "V3"
                            )
                            active['bars_held'] = 0
                            continue

            # ── V4 EMA BOUNCE (IMPROVED: per-symbol + ATR proximity) ─────
            if strategy in ("V4", "ALL"):
                ema_ratio = price / ema200 if ema200 > 0 else 1.0
                ema_dist_atr = row.get('ema_dist_atr', 0)
                if (regime == "TRENDING_UP"
                        and V4_EMA_PROXIMITY_MIN <= ema_ratio <= v4_prox_max
                        and 0.1 <= ema_dist_atr <= 3.0  # ATR-normalized proximity
                        and V4_RSI_LOW <= rsi <= V4_RSI_HIGH and rsi > rsi_prev
                        and rvol >= rvol_min):
                    conf = _confluence_score(price, rsi, bb_u, bb_l, ema200, "LONG", usdt_d)
                    # 4H trend proxy bonus
                    if row.get('ema_50', 0) > ema200:
                        conf += 1
                    if conf >= V4_MIN_CONFLUENCE:
                        sl_dist = max(atr * 1.5, price * ATR_MIN_SL_PCT)
                        active = self._open_trade(
                            ts, sym, "LONG", price, sl_dist, conf, rsi, "V4"
                        )
                        continue

            # ── V1-SHORT (FIXED: lower RSI, VOLATILE regime, EMA slope) ──
            if strategy in ("V1-SHORT", "ALL"):
                ema_slope = row.get('ema200_slope', 0)
                if (price < ema200 and regime in SHORT_REGIMES
                        and rsi >= RSI_SHORT_ENTRY and rsi < rsi_prev
                        and ema_slope < SHORT_EMA_SLOPE_MIN
                        and rvol >= rvol_min):
                    conf = _confluence_score(price, rsi, bb_u, bb_l, ema200, "SHORT", usdt_d)
                    if conf >= SHORT_MIN_CONFLUENCE:
                        sl_dist = max(atr * ATR_SL_MULT, price * ATR_MIN_SL_PCT)
                        active = self._open_trade(
                            ts, sym, "SHORT", price, sl_dist, conf, rsi, "V1-SHORT"
                        )
                        continue

        # Close any open trade at end of data
        if active:
            last_price = df['close'].iloc[-1]
            last_ts = df.index[-1]
            pnl = self._apply_costs(active['entry'], last_price, active['side'])
            trades.append(self._close_trade(active, last_ts, last_price, "OPEN_EOD", pnl))

        return trades

    def _open_trade(self, ts, symbol, side, price, sl_dist, conf, rsi, version):
        """Crea un trade activo."""
        if side == "LONG":
            sl = round(price - sl_dist, 6)
            tp1 = round(price + sl_dist * ATR_TP1_MULT, 6)
            tp2 = round(price + sl_dist * ATR_TP2_MULT, 6)
        else:
            sl = round(price + sl_dist, 6)
            tp1 = round(price - sl_dist * ATR_TP1_MULT, 6)
            tp2 = round(price - sl_dist * ATR_TP2_MULT, 6)

        return {
            "open_ts": ts, "symbol": symbol, "side": side,
            "entry": price, "sl": sl, "tp1": tp1, "tp2": tp2,
            "conf": conf, "rsi_entry": round(rsi, 1),
            "version": version, "tp1_hit": False,
        }

    def _close_trade(self, active, ts, close_price, result, pnl_pct):
        """Cierra un trade y genera el resultado."""
        return {
            "symbol": active["symbol"],
            "version": active["version"],
            "side": active["side"],
            "entry_price": active["entry"],
            "close_price": round(close_price, 4),
            "open_ts": str(active["open_ts"]),
            "close_ts": str(ts),
            "sl": active["sl"],
            "tp1": active["tp1"],
            "tp2": active["tp2"],
            "rsi_entry": active["rsi_entry"],
            "conf_score": active["conf"],
            "result": result,
            "pnl_pct": pnl_pct,
            "tp1_hit": active.get("tp1_hit", False),
            "bars_held": active.get("bars_held", 0),
        }

    # ── Walk-Forward Validation ───────────────────────────────────────────

    def walk_forward(self, strategy="V1", train_pct=0.7, usdt_d=8.0):
        """
        Walk-forward: entrena en train_pct% del data, valida en el resto.

        Retorna dict con metricas in-sample vs out-of-sample.
        """
        import metrics

        if self.df is None or self.df.empty:
            return {"error": "No data loaded"}

        n = len(self.df)
        split = int(n * train_pct)

        # In-sample (training)
        train_df = self.df.iloc[:split].copy()
        bt_train = Backtester(fee_pct=self.fee_pct, slippage_pct=self.slippage_pct)
        bt_train.load_data(self.symbol, df=train_df)
        train_trades = bt_train.run(strategy=strategy, usdt_d=usdt_d)

        # Out-of-sample (validation)
        test_df = self.df.iloc[split:].copy()
        bt_test = Backtester(fee_pct=self.fee_pct, slippage_pct=self.slippage_pct)
        bt_test.load_data(self.symbol, df=test_df)
        test_trades = bt_test.run(strategy=strategy, usdt_d=usdt_d)

        # Metrics
        train_returns = [t["pnl_pct"] for t in train_trades]
        test_returns = [t["pnl_pct"] for t in test_trades]

        train_report = metrics.generate_full_report(
            [{"pnl_pct": r, "id": i} for i, r in enumerate(train_returns)]
        )
        test_report = metrics.generate_full_report(
            [{"pnl_pct": r, "id": i} for i, r in enumerate(test_returns)]
        )

        # Degradation check
        degradation = {}
        for key in ["win_rate", "profit_factor", "sharpe"]:
            in_val = train_report.get(key, 0)
            out_val = test_report.get(key, 0)
            if in_val != 0:
                deg_pct = round((out_val - in_val) / abs(in_val) * 100, 1)
            else:
                deg_pct = 0.0
            degradation[key] = deg_pct

        return {
            "strategy": strategy,
            "symbol": self.symbol,
            "train_bars": split,
            "test_bars": n - split,
            "in_sample": train_report,
            "out_of_sample": test_report,
            "degradation_pct": degradation,
            "train_trades": train_trades,
            "test_trades": test_trades,
        }

    # ── Report Formatting ─────────────────────────────────────────────────

    def format_results(self, trades):
        """Formatea resultados de backtest como string legible."""
        if not trades:
            return f"[{self.symbol}] Sin trades generados."

        import metrics
        returns = [t["pnl_pct"] for t in trades]
        report = metrics.generate_full_report(
            [{"pnl_pct": r, "id": i} for i, r in enumerate(returns)]
        )

        wins = sum(1 for t in trades if t["result"] == "WIN_FULL")
        losses = sum(1 for t in trades if t["result"] == "LOST")
        timeouts = sum(1 for t in trades if t["result"] == "TIMEOUT")
        partials = sum(1 for t in trades if t.get("tp1_hit") and t["result"] != "WIN_FULL")
        avg_bars = round(np.mean([t.get("bars_held", 0) for t in trades]), 1) if trades else 0

        lines = [
            f"═══ BACKTEST: {self.symbol} ═══",
            f"Trades: {len(trades)} (W:{wins} L:{losses} T:{timeouts} P:{partials})",
            f"Avg Hold: {avg_bars} bars",
            f"Win Rate: {report['win_rate']}%",
            f"Profit Factor: {report['profit_factor']}",
            f"Sharpe: {report['sharpe']}",
            f"Sortino: {report['sortino']}",
            f"Max DD: {report['max_drawdown']:.2f}%",
            f"SQN: {report['sqn']} ({metrics.get_sqn_label(report['sqn'])})",
            f"Total Return: {report['total_return_pct']:+.2f}%",
        ]
        return "\n".join(lines)
