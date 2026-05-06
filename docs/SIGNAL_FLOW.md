# SIGNAL_FLOW.md — Zenith Signal Lifecycle

> Última actualización: 2026-05-06  
> Versión: 2.0 (Activate/Skip + Win Rate Sim)

---

## 1. Flujo Completo de una Señal Auto-Detectada

```
┌─────────────────────────────────────────────────────────────┐
│  ESTRATEGIA DETECTA CONDICIÓN (V1/V2/V3/V4/V5)             │
│  strategies.py → evaluate_strategies()                      │
└─────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  _store_pending(sym, side, entry, tp1, tp2, sl, ...)        │
│  scalp_alert_bot._PENDING_SIGNALS[sid] = {...params}        │
│  TTL: 4h. GC automático en cada callback.                   │
└─────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  alert() → Telegram con get_signal_keyboard(sid, sym, side) │
│                                                             │
│   Alerta TAO LONG @ $295.00                                │
│   RSI: 44.2 | TP1: $310 | SL: $280 | Score: 5/6           │
│   ┌────────────────────┬──────────────┐                     │
│   │ ✅ Activar TAO LONG│  ⏭️ Skip     │                     │
│   ├────────────────────┴──────────────┤                     │
│   │ 📊 Ver niveles  │  💰 Budget IA  │                     │
│   └────────────────────────────────────┘                    │
└─────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────┴─────────────┐
              │                          │
              ▼                          ▼
    tap Activar                        tap Skip
     (activate:SID:SYM:SIDE)           (skip:SID:SYM:SIDE)
              │                          │
              ▼                          ▼
  tracker.log_trade(is_sim=0)   tracker.log_simulated(is_sim=1)
  → status: OPEN (REAL)         → status: OPEN (SIM)
              │                  Bot trackea si hubiera ganado
              ▼
  Mensaje se edita con Management Keyboard:
  ┌──────────────┬──────────────┐
  │ ✅ TP1 (50%) │ ✅ TP2 (80%) │
  ├──────────────┼──────────────┤
  │ 🏆 TP3 full  │ 🛑 SL tocado │
  ├──────────────┼──────────────┤
  │🔴 Cerrar@live│ 📊 P&L actual│
  └──────────────┴──────────────┘
```

---

## 2. Flujo Manual via /open (3-tap)

```
Fernando escribe /open
         │
         ▼
Bot responde con picker de símbolos:
  [TAO] [ZEC] [DOGE]
  [SOL] [BTC] [ETH]
  [+ otro]  [cancel]
         │
         ▼ tap [TAO]  (open_sym:TAO)
Bot muestra:
  [🟢 LONG]  [🔴 SHORT]
         │
         ▼ tap [LONG]  (open_side:TAO:LONG)
Bot calcula niveles via ATR y muestra:
  TAO LONG @ $295.00
  SL: $280  TP1: $310  TP2: $325
  [✅ Confirmar] [✏️ Editar entry] [❌ Cancelar]
         │
         ▼ tap [Confirmar]  (open_confirm:TAO:LONG:295.00)
tracker.log_trade(is_manual=1)
Bot edita mensaje con Management Keyboard (mismo que Activar auto-señal)
```

## 3. Flujo Manual via free-text `LONG SYM`

```
Fernando escribe: LONG TAO
         │
         ▼
telegram_commands.py detecta "LONG" + símbolo
Calcula SL/TP via ATR
log_trade(is_manual=1, version="MANUAL")
Envía mensaje con Management Keyboard adjunto
```

---

## 4. Gestión de Trade Abierto (Management Keyboard)

| Botón | Callback | Acción |
|-------|---------|--------|
| ✅ TP1 (50%) | `tp1:TRADE_ID:SYM:SIDE` | status → PARTIAL_WON |
| ✅ TP2 (80%) | `tp2:TRADE_ID:SYM:SIDE` | status → PARTIAL_WON |
| 🏆 TP3 full | `tp3:TRADE_ID:SYM:SIDE` | status → FULL_WON |
| 🛑 SL tocado | `sl:TRADE_ID:SYM:SIDE` | status → LOST |
| 🔴 Cerrar @ live | `close_now:TRADE_ID:SYM:SIDE` | cierra al precio actual, FULL_WON o LOST según PnL |
| 📊 P&L actual | `pnl:TRADE_ID:SYM` | muestra P&L flotante |

**Backward compat:** callbacks legacy (`tp1:SYM:SIDE`, 3 parts) siguen funcionando — buscan last_open_trade(sym).

---

## 5. Definición de Estrategias (Taxonomy)

### Dimensión 1: Source (strategy_version)

| Valor | Generador | Ejemplo |
|-------|-----------|---------|
| `V1-TECH` | Confluencia técnica pura (RSI + BB + EMA200 + ATR) | v1_long, v3_reversal, v4_ema_bounce, v5_momentum |
| `V2-AI` | IA Gemini + confluencia técnica | v2_ai_long, v2_ai_consensus |
| `MANUAL` | Fernando abre manualmente | /open, LONG SYM |
| `SIM` | Señal skiada, bot trackea outcome paper | auto desde skip |
| `COMMODITY` | Bot de commodities (OIL/GOLD) | commodity_conservative |
| `SWING` | Estrategia swing institucional | swing_institutional |

### Dimensión 2: Setup (alert_type)

| Valor | Descripción |
|-------|-------------|
| `v1_long` | RSI < 47 + sobre EMA200 + confluencia ≥ 4 |
| `v1_short` | RSI > 70 + sobre EMA200 + short bias |
| `v3_reversal` | RSI < 28 + bajo EMA200 + régimen VOLATILE/TRENDING_DOWN |
| `v4_ema_bounce` | RSI en zona media (45-55) + precio cerca de EMA200 |
| `v5_momentum` | RSI cruza > 50 desde abajo (momentum shift) |
| `v2_ai_long` | V1-TECH con confirmación AI |
| `v2_ai_consensus` | Consenso 3+ agentes AI |
| `manual_long` / `manual_short` | Apertura manual |
| `manual_migrated` | Migrado desde JSON antiguo |

### Dimensión 3: Macro Regime (campo `note` en trades)

| Valor | SP500 | Comportamiento bot |
|-------|-------|--------------------|
| `VERDE_BULL` | >7,000 | Longs habilitados sin restricción |
| `AMARILLA_INDECISA` | 6,800-7,000 | Reducir tamaño 50% |
| `NARANJA_BEAR` | <6,800 | Activar SHORT SPY, filtrar longs débiles |

---

## 6. Win Rate: Real vs Simulado

```sql
-- Win rate REAL (trades que Fernando activó)
SELECT
  strategy_version, alert_type,
  SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END) as losses,
  ROUND(
    100.0 * SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END)
    / COUNT(*), 1
  ) as wr_pct
FROM trades
WHERE is_sim = 0 AND status NOT IN ('OPEN', 'PARTIAL_WON')
GROUP BY strategy_version, alert_type;

-- Win rate SIMULADO (señales skiadas, bot trackea outcome)
-- Reemplazar WHERE is_sim = 0 → WHERE is_sim = 1
```

Si WR_sim > WR_real → Fernando está skiando señales buenas.
Si WR_sim < WR_real → El filtro humano agrega valor.

---

## 7. Campos clave en `trades`

| Campo | Tipo | Uso |
|-------|------|-----|
| `is_manual` | INTEGER 0/1 | 1 = Fernando abrió manual |
| `is_sim` | INTEGER 0/1 | 1 = señal skiada, paper tracking |
| `strategy_version` | TEXT | Fuente de la señal |
| `alert_type` | TEXT | Setup específico |
| `note` | TEXT | Macro regime + platform + notas |
| `be_moved` | INTEGER 0/1 | SL movido a break even |
| `partial_pct` | INTEGER | % tomado en partial close |
| `events_json` | TEXT | Log de acciones sobre el trade |
| `msg_id` | TEXT | ID mensaje Telegram (para reply/edit) |

---

## 8. Commands Reference

| Comando | Función |
|---------|---------|
| `/open` | Picker inline 3-tap para abrir trade manual |
| `/pos` | Posiciones abiertas (compact: 1 línea por trade) |
| `/pos full` | Posiciones + SL/TP/BE + salud del bot |
| `/manual_tp SYM [pct]` | Cerrar manual completo o parcial |
| `/manual_sl SYM` | Marcar SL hit |
| `/manual_be SYM` | Mover SL a break even |
| `/manual_off SYM` | Detener monitoreo sin cerrar |
| `LONG SYM` / `SHORT SYM` | Abrir manual por texto (con management kb) |
| `CLOSE SYM` / `CERRAR SYM` | Cerrar al precio actual |

---

## 9. Migración desde JSON (legacy)

Si existía `manual_positions.json` de versión anterior:

```bash
cd /path/to/scalp_bot
python3 scripts/migrate_manual_to_db.py
```

Idempotente. Archiva JSON como `.archived` al terminar.
