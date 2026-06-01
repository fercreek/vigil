"""
llm_client.py — Cliente Groq (primario vigilancia) con tracking per-API.

Contexto (2026-06-01): Gemini Flash free tier (250 RPD) + bug JSON "voices empty"
tumbó el Sentinel 202min. Research → venom/reports/llm-api-comparison-2026-06-01.
Decisión B: Groq primario en vigilancia (sentinel + social), Gemini fallback.

- Groq vía REST (OpenAI-compat), sin dep nueva (usa requests).
- gpt-oss-120b → JSON estructurado (constrained decoding, schema strict).
- llama-3.1-8b-instant → texto/social (free tier 14,400 RPD).
- Cada llamada se loguea en ai_budget con provider='groq' → venom monitorea uso per-API.
"""

import os
import json
import requests
from dotenv import load_dotenv
from logger_core import logger
import ai_budget as _budget

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"

# Modelos por rol
GROQ_MODEL_JSON = os.getenv("GROQ_MODEL_JSON", "openai/gpt-oss-120b")
GROQ_MODEL_TEXT = os.getenv("GROQ_MODEL_TEXT", "llama-3.1-8b-instant")

_DEFAULT_TIMEOUT = float(os.getenv("GROQ_TIMEOUT_SEC", "20"))


def groq_available() -> bool:
    return bool(GROQ_API_KEY)


def _strictify_schema(node):
    """
    Groq strict json_schema exige additionalProperties:false en CADA objeto y
    que todas las properties estén en 'required'. Pydantic no lo hace por default.
    Recorre el schema y lo ajusta in-place. Retorna el nodo.
    """
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            props = node.get("properties")
            if isinstance(props, dict) and props:
                node["required"] = list(props.keys())
        for v in node.values():
            _strictify_schema(v)
    elif isinstance(node, list):
        for v in node:
            _strictify_schema(v)
    return node


def _post(payload: dict, timeout: float):
    """POST a Groq chat/completions. Retorna (json_resp, error_str)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(GROQ_BASE, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
        return None, f"{r.status_code} {r.text[:200]}"
    return r.json(), None


def _log_usage(resp: dict, model: str, call_type: str, symbol: str, prompt_len: int):
    try:
        usage = resp.get("usage", {}) if resp else {}
        tin = usage.get("prompt_tokens", 0) or prompt_len // 4
        tout = usage.get("completion_tokens", 0) or 50
        _budget.log_ai_call("groq", model, call_type,
                            tokens_in=tin, tokens_out=tout, symbol=symbol)
    except Exception:
        pass


def groq_text(prompt: str, system: str = "", *,
              model: str = None, temperature: float = 0.7,
              max_tokens: int = 600, call_type: str = "groq_text",
              symbol: str = "", timeout: float = None):
    """
    Generación de texto plano vía Groq. Retorna (texto, ok: bool).
    ok=False → caller debe hacer fallback a Gemini.
    """
    if not groq_available():
        return None, False
    model = model or GROQ_MODEL_TEXT
    timeout = timeout or _DEFAULT_TIMEOUT
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp, err = _post(payload, timeout)
        if err:
            logger.warning(f"[groq_text] {symbol} {model}: {err}")
            return None, False
        _log_usage(resp, model, call_type, symbol, len(prompt))
        text = resp["choices"][0]["message"]["content"].strip()
        if not text:
            return None, False
        return text, True
    except Exception as e:
        logger.warning(f"[groq_text] {symbol} excepción: {e}")
        return None, False


def groq_structured(prompt: str, pydantic_model, *, system: str = "",
                    model: str = None, temperature: float = 0.5,
                    max_tokens: int = 2500, call_type: str = "groq_json",
                    symbol: str = "", timeout: float = None):
    """
    JSON estructurado vía Groq con json_schema strict (constrained decoding).
    Valida contra pydantic_model. Retorna (instancia | None, ok: bool).
    ok=False → caller hace fallback a Gemini.
    """
    if not groq_available():
        return None, False
    model = model or GROQ_MODEL_JSON
    timeout = timeout or _DEFAULT_TIMEOUT
    try:
        schema = _strictify_schema(pydantic_model.model_json_schema())
    except Exception as e:
        logger.warning(f"[groq_structured] schema build fail: {e}")
        return None, False

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": pydantic_model.__name__, "schema": schema, "strict": True},
        },
    }
    try:
        resp, err = _post(payload, timeout)
        if err:
            logger.warning(f"[groq_structured] {symbol} {model}: {err}")
            return None, False
        _log_usage(resp, model, call_type, symbol, len(prompt))
        raw = resp["choices"][0]["message"]["content"]
        data = json.loads(raw)
        obj = pydantic_model(**data)
        return obj, True
    except Exception as e:
        logger.warning(f"[groq_structured] {symbol} parse/validate fail: {e}")
        return None, False


if __name__ == "__main__":
    print("Groq available:", groq_available())
    t, ok = groq_text("Di 'pong' y nada más.", max_tokens=10, symbol="TEST")
    print("text test:", ok, repr(t))
