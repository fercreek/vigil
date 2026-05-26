"""Pydantic models para responses estructuradas de Cuadrilla Zenith.

Spec 005 (2026-05-26) — migración de JSON mode a Structured Output.
Recomendación NotebookLM 4 Prompt 5: elimina errores parseo + enforcement de tipos.
"""

from .sentinel import SentinelResponse, SentinelVoices

__all__ = ["SentinelResponse", "SentinelVoices"]
