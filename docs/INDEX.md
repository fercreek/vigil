# Docs Index — Scalp Bot / Zenith

Todos los documentos del repo categorizados. Entry point: [README.md](../README.md).

---

## 🚀 Operación (día a día)

| Doc | Qué contiene |
|-----|-------------|
| [DEV_WORKFLOW.md](DEV_WORKFLOW.md) | Flujo diario: dev branch, BOT_MODE=DEV, predeploy-check, agregar símbolo/dep/env |
| [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md) | Runbook formal dev→main→Railway. Rollback. Raw Editor Railway |
| [ENV_REFERENCE.md](ENV_REFERENCE.md) | Tabla exhaustiva de todas las env vars (PROD/DEV, Railway vs .env) |
| [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) | Comandos Telegram runtime (`/pause`, `/mode`, `/status`, `/logs`) |
| [DEPLOY_STATUS.md](DEPLOY_STATUS.md) | Checkpoint histórico del deploy a Railway (Apr 2026) |
| [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) | Setup inicial Railway (build, healthcheck, env vars) |

---

## 📈 Estrategia

| Doc | Qué contiene |
|-----|-------------|
| [STRATEGY_RULES.md](STRATEGY_RULES.md) | Reglas operativas — Antigravity-based filtering (2026-03-30) |
| [STRATEGY_AUDIT.md](STRATEGY_AUDIT.md) | Auditoría de win rate por símbolo + iteración de filtros |
| [ZENITH_MANIFESTO_V10.md](ZENITH_MANIFESTO_V10.md) | Filosofía del bot V1→V10. Evolución de la Cuadrilla AI |

---

## 🧪 Simulación + backtesting

| Doc | Qué contiene |
|-----|-------------|
| [SIMULATION_GUIDE.md](SIMULATION_GUIDE.md) | Cómo correr simulaciones con histórico real |
| [PINE_SCRIPT_GUIDE.md](PINE_SCRIPT_GUIDE.md) | Desarrollo de Pine Scripts para TradingView V18 |
| `zenith_indicator.pine` | Pine Script actual del indicador Zenith V18 |

---

## 🔌 Integraciones

| Doc | Qué contiene |
|-----|-------------|
| [TRADINGVIEW_WEBHOOK.md](TRADINGVIEW_WEBHOOK.md) | Webhook TV: HMAC, token, rate limit, Pine payload |
| [REPLIT_GUIDE.md](REPLIT_GUIDE.md) | Legacy — setup en Replit (pre-Railway, archivado) |

---

## 🏗 Arquitectura

| Doc | Qué contiene |
|-----|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design: threads, DBs, AI Router, flujo de señales |

---

## 📊 Intel de mercado (PTS + BitLobo)

| Archivo | Qué contiene |
|---------|-------------|
| `pts_transcript.es.vtt` | Transcript bruto de live PTS (YouTube) |
| `pts_transcript_clean.txt` | Transcript limpio — usado para alimentar FOMC_CONTEXT |
| `reporte_ayer.md` | Reporte diario de señales + WR |
| `reports/` | Histórico de reportes post-mortem |
| `archive_trades_v1_v11.db` | DB histórica de trades pre-v4 (archivada) |

---

## Meta-contexto

Este proyecto vive bajo el marco personal de Fernando. Ver:
- `~/Documents/context/CLAUDE.md` §11 — Cortex Consejo
- `~/.claude/plugins/cortex-consejo/` — plugin multi-voz
- `/CLAUDE.md` (raíz repo) — instrucciones específicas del bot

Para decisiones estratégicas (agregar sector, cambiar threshold, abrir cuenta, matar feature) correr `/consejo [decisión]` antes de ejecutar.
