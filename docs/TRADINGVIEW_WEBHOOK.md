# TradingView Webhook — Runbook

Setup + operación del endpoint `/webhook/tradingview` endurecido en F1.

## Arquitectura

```
TradingView Pine Script
  │ alerta dispara
  ▼
POST https://bot.dominio/webhook/tradingview[/<token>]
  │
  ▼ app.py:417  @require_tv_auth
  ├── Rate limit (10 req/min por IP)
  ├── HMAC SHA256 verify (X-TV-Signature)   ← enforce opcional
  ├── Token path verify (/webhook/tradingview/<TOKEN>)   ← 2º factor
  └── Idempotency (hash payload+minuto)
  │
  ▼ tradingview_webhook()
  ├── Parse JSON (symbol, direction, rsi, price, strategy, confidence)
  ├── signal_coordinator.submit("TRADINGVIEW", ...)
  └── resolve_and_send(symbol, alert_manager.send_telegram)
```

## Auth: 3 capas

### 1. HMAC SHA256 (publishers que pueden firmar)

Cliente computa firma:
```python
import hmac, hashlib
sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
# → enviar en header: X-TV-Signature: <sig>
```

Server reconstruye firma con mismo secret. `hmac.compare_digest` = constant-time compare (no timing attacks).

### 2. Token path (Pine Script TV — no puede HMAC)

TradingView Pine no expone hashing — usar segundo factor:
```
POST /webhook/tradingview/<TV_WEBHOOK_TOKEN>
```

Token aleatorio 24 bytes urlsafe. Rotar cada 90 días.

### 3. Rate limit + idempotency

- Rate limit: `TV_RATE_LIMIT_PER_MIN=10` por IP → 429 si exceded
- Idempotency: `sha256(payload + minuto_actual_unix)` → reject duplicados 5 min

## Variables `.env`

```bash
TV_WEBHOOK_SECRET=<32 bytes hex>      # HMAC key
TV_WEBHOOK_TOKEN=<24 bytes urlsafe>   # path token
ENFORCE_HMAC=false                    # canary; true en prod después validar
TV_RATE_LIMIT_PER_MIN=10
```

Generar secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Guardar ambos en password manager. **Nunca** commitear.

## Setup TradingView UI

1. Pine Editor → pegar `scripts/tradingview/Zenith_Suite_V18.pine`
2. Add to Chart
3. Crear alerta:
   - Condition: `Zenith V18 → Any alert() function call`
   - Notifications → Webhook URL:
     ```
     https://bot.dominio/webhook/tradingview/<TV_WEBHOOK_TOKEN>
     ```
   - Message body:
     ```json
     {
       "symbol": "{{ticker}}",
       "direction": "{{strategy.order.action}}",
       "rsi": {{plot("RSI")}},
       "price": {{close}},
       "strategy": "Zenith V18",
       "confidence": 0.9
     }
     ```
4. Save alert. Frequency = `Once Per Bar Close` (evita spam).

## Testing

### Local (canary ENFORCE_HMAC=false)

```bash
# Arrancar bot + Flask local
source venv/bin/activate
python scalp_alert_bot.py &
python app.py &

# Test sin firma (debe pasar con canary off)
curl -X POST http://localhost:5001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'
# → {"ok":true,"symbol":"BTC","direction":"LONG","sent":...}
```

### Local (ENFORCE_HMAC=true)

```bash
export ENFORCE_HMAC=true
# restart bot

# Sin firma → 401
curl -X POST http://localhost:5001/webhook/tradingview -d '{}'
# → 401 {"ok":false,"error":"unauthorized"}

# Con HMAC válido
SECRET="$TV_WEBHOOK_SECRET"
PAYLOAD='{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST http://localhost:5001/webhook/tradingview \
  -H "X-TV-Signature: $SIG" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
# → 200

# Con token path
curl -X POST "http://localhost:5001/webhook/tradingview/$TV_WEBHOOK_TOKEN" \
  -H "Content-Type: application/json" -d "$PAYLOAD"
# → 200

# Rate limit
for i in {1..15}; do
  curl -X POST "http://localhost:5001/webhook/tradingview/$TV_WEBHOOK_TOKEN" \
    -H "Content-Type: application/json" -d "$PAYLOAD"
done
# → req 11+ devuelve 429
```

### Producción (post F3)

Cambiar `localhost:5001` → `bot.dominio`.

## Activar enforce en producción

Después de validar que alertas TV firman correctamente:

1. Editar `.env` en VPS: `ENFORCE_HMAC=true`
2. `ssh scalpbot "sudo systemctl restart scalpbot"`
3. Tail logs: `journalctl -u scalpbot -f | grep "TV webhook"`
4. Disparar alerta TV manual → verificar que llega

## Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| 401 unauthorized | `ENFORCE_HMAC=true` + firma mala o token mal | verificar secret/token env |
| 429 rate_limit | IP excedió 10/min | esperar 60s, o subir `TV_RATE_LIMIT_PER_MIN` |
| 200 `duplicate: true` | mismo payload mismo minuto | comportamiento correcto; TV no debería repetir |
| 500 error | parsing JSON o signal_coordinator fallo | `journalctl -u scalpbot -n 100` |
| Alerta llega pero no hay mensaje TG | confluencia insuficiente en `signal_coordinator` | revisar `alert_manager.send_telegram` logs |

## Rotar secret/token

```bash
# 1. Generar nuevo
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# 2. Actualizar .env en VPS
ssh scalpbot "sed -i 's/TV_WEBHOOK_SECRET=.*/TV_WEBHOOK_SECRET=$NEW_SECRET/' ~/scalp_bot/.env"

# 3. Restart
ssh scalpbot "sudo systemctl restart scalpbot"

# 4. Actualizar URL en TradingView UI con nuevo token
# 5. Actualizar secret en password manager
```
