"""
webhook_security.py — Auth layer para webhook TradingView.

Tres capas:
1. HMAC SHA256 — header `X-TV-Signature` vs payload firmado con secret
2. Rate limit — N requests/min por IP (in-memory, TTL 60s)
3. Idempotency — hash(payload+minuto) reject duplicados

Flag `ENFORCE_HMAC=false` default (canary). Activar tras validar Pine firma OK.
Token path `/webhook/tradingview/<token>` = segundo factor si Pine no puede HMAC.
"""

import hmac
import hashlib
import os
import time
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify

try:
    from logger_core import logger
except Exception:
    import logging
    logger = logging.getLogger("webhook_security")

# ── Config (lee env con fallbacks seguros) ────────────────────────────────────
TV_WEBHOOK_SECRET = os.getenv("TV_WEBHOOK_SECRET", "")
TV_WEBHOOK_TOKEN = os.getenv("TV_WEBHOOK_TOKEN", "")  # segundo factor opcional
ENFORCE_HMAC = os.getenv("ENFORCE_HMAC", "false").lower() == "true"
TV_RATE_LIMIT_PER_MIN = int(os.getenv("TV_RATE_LIMIT_PER_MIN", "10"))

# ── Rate limiter in-memory ────────────────────────────────────────────────────
_rate_buckets: dict[str, deque] = defaultdict(lambda: deque(maxlen=TV_RATE_LIMIT_PER_MIN * 2))

# ── Idempotency cache ─────────────────────────────────────────────────────────
_idempotency_seen: dict[str, float] = {}
_IDEMPOTENCY_TTL = 300  # 5 min


def _client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _verify_hmac(payload: bytes, signature: str) -> bool:
    if not TV_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(TV_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= TV_RATE_LIMIT_PER_MIN:
        return True
    bucket.append(now)
    return False


def _is_duplicate(payload: bytes) -> bool:
    key = hashlib.sha256(payload + str(int(time.time() // 60)).encode()).hexdigest()
    now = time.time()
    for k in list(_idempotency_seen.keys()):
        if now - _idempotency_seen[k] > _IDEMPOTENCY_TTL:
            _idempotency_seen.pop(k, None)
    if key in _idempotency_seen:
        return True
    _idempotency_seen[key] = now
    return False


def require_tv_auth(f):
    """Decorador para endpoints webhook TradingView."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = _client_ip()

        if _rate_limited(ip):
            logger.warning(f"[TV webhook] Rate limit IP={ip}")
            return jsonify({"ok": False, "error": "rate_limit"}), 429

        payload = request.get_data() or b""

        url_token = kwargs.get("token")
        token_ok = bool(TV_WEBHOOK_TOKEN) and url_token == TV_WEBHOOK_TOKEN
        sig = request.headers.get("X-TV-Signature", "")
        hmac_ok = _verify_hmac(payload, sig)

        if ENFORCE_HMAC and not (hmac_ok or token_ok):
            logger.warning(f"[TV webhook] Auth failed IP={ip} hmac={hmac_ok} token={token_ok}")
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        if _is_duplicate(payload):
            logger.info(f"[TV webhook] Duplicate IP={ip}")
            return jsonify({"ok": True, "duplicate": True}), 200

        logger.info(f"[TV webhook] Accepted IP={ip} hmac={hmac_ok} token={token_ok} enforce={ENFORCE_HMAC}")
        kwargs.pop("token", None)
        return f(*args, **kwargs)
    return wrapper
