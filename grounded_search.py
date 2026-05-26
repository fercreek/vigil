"""grounded_search.py — Gemini Grounding with Google Search.

Spec 014 (2026-05-26 — NotebookLM 4 Prompt 5): aprovechar Gemini Flash 2.5 Grounding
para que la voz Apocalipsis (riesgo macro) pueda hacer queries en tiempo real
sobre eventos como decisiones FOMC, crisis geopolíticas, tariff news.

Reemplaza el actual "Web fetch para FOMC PDFs" + reportes BlackRock manual del bot.
Le da a Apocalipsis contexto en tiempo real sin programar scrapers.

Costo: Gemini cobra Grounding adicional ($0.50/1k queries aprox). Con el presupuesto
$10/mes del bot, capamos manualmente con `GROUNDED_SEARCH_DAILY_CAP = 5` consultas/día.
Si se excede el cap, fallback a `None` y la voz Apocalipsis usa contexto hardcoded.

Uso típico:
    from grounded_search import query_grounded_search
    macro_context = query_grounded_search(
        query="latest FOMC decision rate June 2026",
        intent_label="apocalipsis_macro_fomc",
    )
    if macro_context:
        # Inyectar a prompt de Apocalipsis
        prompt += f"\nNEWS HOY: {macro_context}\n"
    # Si None: usar FOMC_CONTEXT hardcoded del bot
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional

try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

try:
    from logger_core import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    import ai_budget as _budget
    _BUDGET_AVAILABLE = True
except ImportError:
    _BUDGET_AVAILABLE = False


# ── Constantes ──────────────────────────────────────────────────────────────
GROUNDED_SEARCH_DAILY_CAP = 5         # max queries/día (proteger budget)
GROUNDED_SEARCH_MODEL = "gemini-2.5-flash"
GROUNDED_SEARCH_TIMEOUT = 15.0
GROUNDED_SEARCH_MAX_TOKENS = 400      # respuesta concisa

# Cache simple en memoria — evita queries duplicadas dentro de la misma hora
_CACHE: dict = {}
_CACHE_TTL = 3600  # 1h

# Contador in-memory (se resetea con bot restart). Para persistencia real,
# usar ai_budget DB. Spec 014.5 candidate.
_DAILY_COUNTER: dict[str, int] = {}


def _today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_daily_count() -> int:
    """Retorna conteo de queries grounded del día actual."""
    return _DAILY_COUNTER.get(_today_key(), 0)


def _increment_daily_count():
    """Incrementa conteo. Reinicia automático al cambiar de día."""
    today = _today_key()
    _DAILY_COUNTER[today] = _DAILY_COUNTER.get(today, 0) + 1
    # Cleanup: mantener solo las últimas 7 entradas
    if len(_DAILY_COUNTER) > 7:
        oldest = sorted(_DAILY_COUNTER.keys())[:-7]
        for k in oldest:
            del _DAILY_COUNTER[k]


def _cache_get(query: str) -> Optional[str]:
    """Retorna cached result si todavía válido."""
    entry = _CACHE.get(query)
    if entry is None:
        return None
    if time.time() - entry["ts"] > _CACHE_TTL:
        del _CACHE[query]
        return None
    return entry["result"]


def _cache_set(query: str, result: str):
    """Guarda result en cache."""
    _CACHE[query] = {"ts": time.time(), "result": result}
    # Cleanup: max 50 entries
    if len(_CACHE) > 50:
        oldest = sorted(_CACHE.items(), key=lambda x: x[1]["ts"])[:10]
        for k, _ in oldest:
            del _CACHE[k]


def query_grounded_search(
    query: str,
    intent_label: str = "grounded_search",
    daily_cap: int = GROUNDED_SEARCH_DAILY_CAP,
) -> Optional[str]:
    """
    Ejecuta query con Gemini Grounding + Google Search habilitado.

    Args:
        query: La consulta en lenguaje natural. Ej "latest FOMC decision rate June 2026".
        intent_label: Etiqueta semántica para tracking (ej "apocalipsis_macro_fomc").
            Usada en logs + ai_budget logging.
        daily_cap: Máximo queries/día. Default = GROUNDED_SEARCH_DAILY_CAP (5).

    Returns:
        str con texto sintético del modelo (con grounding), o None si:
          - Genai SDK no disponible
          - GEMINI_API_KEY no configurada
          - Daily cap excedido
          - Query falla por timeout/error

    Notas:
        - Cache 1h por query exacta (no consume cap si hit cache)
        - Increments _DAILY_COUNTER solo si query realmente fue a la API
        - Logs el uso vía ai_budget si está disponible
    """
    if not _GENAI_AVAILABLE:
        logger.warning("[grounded_search] google.genai no disponible — skip")
        return None

    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("[grounded_search] GEMINI_API_KEY no configurada — skip")
        return None

    # Cache hit no cuenta contra cap
    cached = _cache_get(query)
    if cached is not None:
        logger.info(f"[grounded_search] cache hit ({intent_label}): {query[:60]}")
        return cached

    # Cap check
    used_today = _get_daily_count()
    if used_today >= daily_cap:
        logger.warning(
            f"[grounded_search] daily cap reached ({used_today}/{daily_cap}) — skip query: {query[:60]}"
        )
        return None

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        # Habilitar Google Search tool
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        response = client.models.generate_content(
            model=GROUNDED_SEARCH_MODEL,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                temperature=0.3,
                max_output_tokens=GROUNDED_SEARCH_MAX_TOKENS,
                system_instruction=(
                    "Responde en español, conciso (máximo 4 oraciones). "
                    "Cita la fuente brevemente. Si no hay info reciente, di 'sin datos recientes'."
                ),
            ),
        )

        result = (response.text or "").strip()
        if not result:
            logger.warning(f"[grounded_search] respuesta vacía: {query[:60]}")
            return None

        # Incrementar counter SOLO en hit a la API
        _increment_daily_count()
        _cache_set(query, result)

        # Log to budget tracker si disponible
        if _BUDGET_AVAILABLE:
            try:
                meta = getattr(response, "usage_metadata", None)
                tokens_in = getattr(meta, "prompt_token_count", 0) if meta else 0
                tokens_out = getattr(meta, "candidates_token_count", 0) if meta else 0
                _budget.log_ai_call(
                    provider="gemini",
                    model=GROUNDED_SEARCH_MODEL,
                    call_type=f"grounded_{intent_label}",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cached_tokens_in=0,
                    symbol="",
                    approved=True,
                )
            except Exception as _e:
                logger.warning(f"[grounded_search] budget log failed: {_e}")

        logger.info(
            f"[grounded_search] OK ({intent_label}) [{used_today + 1}/{daily_cap}]: {query[:60]}"
        )
        return result

    except Exception as e:
        logger.error(f"[grounded_search] error querying ({intent_label}): {e}")
        return None


def get_daily_usage() -> dict:
    """Helper para debug/telemetría: retorna conteo del día + cap."""
    return {
        "date": _today_key(),
        "used": _get_daily_count(),
        "cap": GROUNDED_SEARCH_DAILY_CAP,
        "cache_size": len(_CACHE),
    }
