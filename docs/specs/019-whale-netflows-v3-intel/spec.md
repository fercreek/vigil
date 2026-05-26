# Spec 019 — Whale Netflows en V3 INTEL Injection

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — wire Spec 010 onchain.get_whale_netflow a producción
> **Origen:** Spec 010.5 backlog + Spec 017 extension

## Contexto

Spec 010 dejó `onchain.get_whale_netflow` standalone para Etherscan/BscScan. Backlog 010.5 sugería wire a voz Genesis (capital institucional).

Spec 019 extiende Spec 017 (INTEL injection) agregando whale netflow al `_extra_intel` dict cuando el símbolo es trackeable on-chain. Hoy solo **ETH** (Etherscan directo). BTC y otros tokens nativos sin chain match → skip silent.

## Goals

1. En `strategies.py:V3-REVERSAL` bloque INTEL builder:
   - Si `sym.replace("/USDT","") == "ETH"` → fetch `onchain.get_whale_netflow("ETH", "eth", 24)`
   - Agregar `whale_signal` y `whale_net_flow_usd` al `_extra_intel`
2. Extender `_format_extra_intel` en `gemini_analyzer.py`:
   - Si key `whale_signal` presente → línea "📡 Whale netflow 24h ETH on-chain (Genesis): $X · signal=Y"
3. Try/except graceful — failure no afecta resto del INTEL

## Non-goals

- BTC/SOL/ZEC/TAO whale tracking (sin chain match Etherscan/BscScan)
- Background polling whale netflow — solo on-demand en V3 trigger
- Wire en V2-AI/V4/SWING — solo V3 este spec
- Customizar threshold `WHALE_NETFLOW_BEARISH_USD` per-V3-call — usa defaults Spec 010

## Dependencias

- `onchain.get_whale_netflow` ✅ (Spec 010)
- `gemini_analyzer._format_extra_intel` ✅ (Spec 017)
- `strategies.py:V3-REVERSAL INTEL builder` ✅ (Spec 017)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Etherscan API rate limit en cada V3 ETH trigger | Cache 5min en `onchain.py`. V3 ETH triggers raros — overhead negligible |
| ETHERSCAN_API_KEY env var no configurada en Railway | `onchain` retorna {} → `_extra_intel` sin whale key → bloque INTEL muestra solo HMM/CVD/Social |
| Whale fetch tarda >5s y bloquea V3 | Timeout 8s (Spec 010 config) + try/except — V3 sigue normal con bloque parcial |
| Otros símbolos (BTC) no tienen whale data | Skip silent. Bloque INTEL muestra 3 líneas en lugar de 4 |

## Criterio de aceptación

1. `python3 -m py_compile gemini_analyzer.py strategies.py` → OK
2. Smoke `_format_extra_intel(full_with_whale)` → 4 líneas (HMM + CVD + Social + Whale)
3. Smoke `_format_extra_intel(without_whale)` → 3 líneas (sin línea whale)
4. V3-REVERSAL solo fetch whale si `sym_base == "ETH"`
5. Producción pendiente: próxima alerta V3 ETH → Telegram muestra línea whale en INTEL block
