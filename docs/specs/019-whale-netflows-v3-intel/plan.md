# Plan 019 — Whale Netflows V3 INTEL

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Solo ETH por ahora (no BTC/SOL/ZEC/TAO)

Etherscan + BscScan tracking nativo de ETH/BNB chains. BTC necesita blockchain.com o Glassnode (API key paid). SOL tiene Solana RPC distinto. ZEC/TAO sin equivalente directo.

Filtro temprano: `if _sym_base == "ETH"`. Para otros símbolos, _whale queda {} y el extra_intel no incluye keys whale.

Spec 019.5 candidato: agregar BTC via blockchain.com explorer API + SOL via SolanaFM gratis.

### 2. NO usar whale netflow como GATE en este spec

Aunque BEARISH netflow (inflows masivos a exchanges) sería kill condition lógico para V3 LONG, este spec NO agrega gate. Razón:
- Spec 016 ya tiene 4 gates (funding + HMM + CVD + Social) — agregar 5to puede killear alertas en exceso
- Spec 019 enfocado en visibilidad/contexto, no en filtering
- Spec 019.5 candidate gate si los wires actuales muestran que whale BEARISH consistentemente coincide con bad V3 LONGs

### 3. Cache 5min del módulo onchain.py

Una llamada Etherscan ~1-2s. Si V3 ETH triggerea c/15min (frecuencia normal RSI extremo) y cache 5min → 5min cache covers 1-2 triggers, then refresh. Sustainable rate limit.

### 4. Datos minimos en `_extra_intel`

Solo `whale_signal` y `whale_net_flow_usd`. NO tx_count, NO last_update_ts, etc. Razón:
- Cuadrilla Zenith voces tienen máx 12 palabras
- Magnitud + dirección suficiente para contexto
- Menos tokens en prompt = mejor cache hit Gemini

### 5. Línea en INTEL block con mapeo Genesis

```
• Whale netflow 24h ETH on-chain (Genesis): $-15,000,000 · signal=BULLISH
```

`(Genesis)` indica qué voz lo lee. Genesis = capital institucional = whales. Match perfecto.

Negative net_flow_usd = OUTFLOW neto = bullish (whales acumulando, sacando de exchanges).

## Verificación

- ✅ py_compile gemini_analyzer.py strategies.py
- ✅ `_format_extra_intel` con whale_signal → línea 4
- ✅ `_format_extra_intel` sin whale → 3 líneas (sin error)
- ✅ V3-REVERSAL filtra por `sym_base == "ETH"`

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(onchain): spec-019 whale netflows en V3 INTEL injection (ETH only)` |

## Backlog Spec 019.5

- Agregar BTC via blockchain.com API (gratis con rate limits)
- Agregar SOL via SolanaFM gratis
- Whale gate (BEARISH → kill V3 LONG) post-validación 7d
- Whale netflow trend (5d slope no solo current 24h)
- Visualización en dashboard Spec 015 (`/api/metrics/onchain_eth`)
