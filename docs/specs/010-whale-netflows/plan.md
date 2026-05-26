# Plan 010 — Whale Netflows On-Chain Tracker

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Módulo nuevo standalone (`onchain.py`) análogo a `market_intel.py`. Cero modificaciones a archivos existentes excepto `config.py` (append 4 constantes). Wire futuro en gemini_analyzer/strategies = Spec 010.5.

## Decisiones técnicas

### 1. Etherscan/BscScan endpoint elegido: `txlist` (tx normales)

`txlist` retorna las últimas 100 transacciones nativas (ETH/BNB) de una address. Más simple que `tokentx` (ERC-20) y suficiente para tracking de whale ETH/BNB depósitos.

Trade-off aceptado: USDT/USDC stablecoin flows requieren `tokentx` — futuro Spec 010.5.

### 2. Cache key por (token, chain, lookback) — no per-wallet

Una llamada a `get_whale_netflow("ETH", "eth", 24)` itera 5 wallets internamente y agrega. El cache es del agregado, no por-wallet. Ratio: a las 5 calls/sec, 5 wallets = 1 segundo. Con TTL 300s tenemos margen 60x.

### 3. Threshold $10M ÷ $1M dual

Dos thresholds independientes:
- `min_value_usd=1_000_000` per-tx filter — descarta retail noise (movimientos <$1M no son whale)
- `WHALE_NETFLOW_BEARISH_USD=10_000_000` agregado-direccional — net en ventana 24h

Lógica: muchos whales de $1-3M sumando en una dirección = señal. Una sola tx de $1M no.

### 4. Precio USD vía Binance Futures (lazy import)

```python
from exchange_singleton import binance_futures
ticker = binance_futures.fetch_ticker("ETH/USDT:USDT")
```

Razón: el bot ya tiene este singleton inicializado, gratis, sin extra API. Si falla → log warning + return `{}`.

### 5. Iteración por wallets, NO async/parallel

Free tier rate limit: 5 calls/sec total. 5 wallets secuencial = 1 segundo, suficiente. Async paralelo arriesga 429 rate limit ban.

### 6. Filtrado de tx antes de cutoff con early break

Etherscan retorna `sort=desc` (más reciente primero). Al primer `tx_ts < cutoff_ts` → break del loop. Evita procesar tx viejas innecesariamente.

### 7. `signal` classification simple (sin smoothing)

`net_flow_usd` directamente comparado contra thresholds. No EMA / rolling avg porque:
- Cache 5min ya provee smoothing implícito (snapshot estable)
- Lookback 24h es la ventana — smoothing extra sería redundante

### 8. Degradación graceful — return `{}` no excepción

Patrón de `market_intel.py`: si falla todo, return dict vacío. Caller hace `if data: ...`. Sin esto, una mala llamada a Etherscan colgaría hook futuro en Cuadrilla.

## Verificación

- ✅ py_compile onchain.py config.py
- ✅ AST: funciones públicas y privadas presentes
- ✅ from config import 4 constantes
- ✅ from onchain import get_whale_netflow sin side effects
- ⏳ Test real con Etherscan API → posponer (no API key en env, riesgo de rate limit en dev)

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(onchain): spec-010 whale netflows tracker (Etherscan + BscScan)` |

## Tuning post-7d (cuando Spec 010.5 wire)

- Si threshold $10M dispara <2x/semana → bajar a $5M
- Si dispara >10x/semana → subir a $20M (ruido)
- Si BEARISH signal correlaciona con drawdown >2% en 6h posteriores → alta confianza, candidato wire automático
- Si NEUTRAL >80% del tiempo → reducir lookback de 24h a 12h para más sensibilidad
