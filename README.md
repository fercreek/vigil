# Zenith Trading Suite — Scalp Bot

Bot personal de trading algorítmico 24/7. Análisis técnico híbrido + IA (Gemini) + webhook TradingView. Opera cripto (BTC, ZEC, SOL, ETH) + commodities (GOLD, OIL) + watchdog de acciones NYSE/NASDAQ.

![deploy](https://img.shields.io/badge/deploy-Railway-success) ![version](https://img.shields.io/badge/version-v4.2-blue) ![wr](https://img.shields.io/badge/WR-62%25-brightgreen) ![mode](https://img.shields.io/badge/exec-PAPER-yellow)

---

## Estado

- **Prod:** Railway `gentle-endurance` → auto-deploy desde `main`. Healthcheck `/api/stats` OK.
- **Tag actual:** `v1.0.0` (commit `07245f4` — first Railway deploy)
- **Iteración:** Strategy v4.2 | WR proyectado ~62% | 77 trades reales analizados
- **Símbolos activos:** ZEC, BTC, SOL, GOLD, OIL (ETH/DOGE/HBAR monitoreados)
- **Kill switches:** TAO (0% WR en 28 trades), V1-SHORT (0% WR en 16 trades)

---

## Arquitectura

```
                        ┌─────────────┐
                        │  main.py    │  BOT_MODE resolver → PROD/DEV
                        │  (entry)    │  arranca 5 threads daemon
                        └──────┬──────┘
                               │
      ┌───────────────┬────────┼────────┬───────────────┬──────────────┐
      ▼               ▼        ▼        ▼               ▼              ▼
┌───────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────┐
│ scalp_bot │ │  swing_bot   │ │stock_analyzer│ │commodities_bot │ │ telegram │
│ (1m-15m)  │ │    (4H)      │ │   (15m-1H)   │ │   (GOLD/OIL)   │ │  worker  │
└─────┬─────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────┘ └────┬─────┘
      │              │                │                   │              │
      └──────────────┴────────┬───────┴───────────────────┘              │
                              ▼                                           │
                    ┌──────────────────┐                                  │
                    │ gemini_analyzer  │◀──── Cuadrilla Zenith           │
                    │  (AI consensus)  │      (Genesis, Exodo,           │
                    └────────┬─────────┘       Salmos, Apocalipsis)      │
                             │                                            │
                             ▼                                            │
                    ┌──────────────────┐                                  │
                    │ trading_executor │──▶ Binance (PAPER o LIVE)       │
                    └──────────────────┘                                  │
                                                                          │
                    ┌──────────────────┐                                  │
                    │   Flask (app)    │◀── webhook TV + /api/stats ◀────┘
                    │   :8080          │
                    └──────────────────┘
```

---

## Quick start

```bash
git clone git@github.com:fercreek/vigil.git scalp_bot
cd scalp_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Rellenar: TELEGRAM_TOKEN_DEV, TELEGRAM_CHAT_ID_DEV, GEMINI_API_KEY
# Ver docs/ENV_REFERENCE.md

BOT_MODE=DEV python main.py
# Banner: [BOOT] BOT_MODE=DEV — using dev token + EXECUTION_MODE=PAPER forced
```

**Primera vez:** registrar `@ZenithDevBot` en @BotFather — ver [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md#registrar-bot-dev-zenithdevbot--primera-vez).

---

## Ciclo de trabajo

```
dev (default) ──▶ edit ──▶ test local ──▶ predeploy-check.sh ──▶ merge main ──▶ Railway auto-deploy
```

| Fase | Doc |
|------|-----|
| Desarrollo diario | [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md) |
| Deploy a prod | [docs/DEPLOY_CHECKLIST.md](docs/DEPLOY_CHECKLIST.md) |
| Env vars | [docs/ENV_REFERENCE.md](docs/ENV_REFERENCE.md) |
| Comandos runtime | [docs/COMMAND_REFERENCE.md](docs/COMMAND_REFERENCE.md) |
| Todo lo demás | [docs/INDEX.md](docs/INDEX.md) |

**Gate pre-merge (30s):**
```bash
./scripts/predeploy-check.sh
# 6 checks: syntax, imports, requirements, tests, .env guard, TODOs críticos
```

---

## Filtros activos v4.2

Horas bloqueadas (UTC) — 0% WR histórico:
`01, 04, 06, 10, 11, 14, 15, 16, 17, 20`

Entry guards por ciclo:
1. **Hour filter** — bloquea entradas en horas con 0% WR
2. **EMA50 trend** — LONG solo si precio > EMA50 en 4H (swing)
3. **Consecutive-loss guard** — pausa símbolo tras 2 pérdidas SWING seguidas
4. **Time exit** — cierra trades a las 36h si no llegaron a TP/SL
5. **Circuit breaker** — pausa global tras X pérdidas consecutivas
6. **FOMC filter** — reduce señales en ventana FOMC (ver `config.py`)
7. **Funding rate** — bloquea si funding extremo (crowded trade)

---

## Win Rate — Historial

Análisis sobre 77 trades reales (Mar-Abr 2026):

| Iteración | Filtros | WR | Commit |
|-----------|---------|-----|--------|
| Baseline | ninguno | 18.2% | — |
| v4.0 | Mighty Snail (ADX, BB, RVOL, RSI) | — | `98ff7cd` |
| v4.1 | Kill switches + SIM D2 hour filter | 50.0% | `8c19d5e` |
| **v4.2** | + EMA50 trend + consecutive-loss guard | **~62% proyectado** | `307d225` |

Target real: **60-65% WR con R:R 1.5** = break-even en 40%, edge real en +20pp.
**80% WR en muestras <200 trades = overfitting.**

---

## Stack técnico

- **Lenguaje:** Python 3.12
- **Runtime:** Flask + 5 threads daemon + watchdog auto-restart
- **Exchange:** Binance Futures vía ccxt (HMAC auth)
- **IA:** Gemini (Pro + Vision) + Claude Haiku opcional (AI Router con fallback)
- **Data:** yfinance (stocks + commodities) + Binance klines (crypto)
- **Infra:** Railway (nixpacks builder, Europe West 4)
- **Tests:** pytest (fixtures OHLCV sintéticos, sin red)

---

## Meta-contexto — Cortex Consejo

Este proyecto vive bajo el marco operativo personal de Fernando. Ver `~/Documents/context/CLAUDE.md` §11 y el plugin `~/.claude/plugins/cortex-consejo/`. La Cuadrilla Zenith en `gemini_analyzer.py` es la prueba validada del patrón multi-voz que inspiró el plugin.

Para decisiones estratégicas (agregar sector, cambiar threshold, abrir nueva cuenta, matar feature) correr `/consejo [decisión]` antes de ejecutar.

Axiomas aplicables:
- **Sabiduría > instinto** — bot ya implementa con filtros de confluencia (no tomar señal solo por RSI).
- **Su suerte no está donde usted trabaja** (Odi Sa) — si TAO lleva 0% WR, cuestionar si seguir ahí.
- **Hacer negocio solo** (Ojuani Tanshela) — ejecutar con cuenta propia, no partnerships.

---

## Licencia

Privado. Uso personal de Fernando Castañeda.
