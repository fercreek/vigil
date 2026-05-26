"""PanoramaPersonaResponse — Pydantic v2 schema para output por persona de get_hourly_panorama.

Spec 005.5 (2026-05-26): extiende Spec 005 (SentinelResponse) a la llamada de Panorama horario.
Cada persona (CONSERVADOR, SCALPER, SALMOS, APOCALIPSIS) responde con:
    BIAS: ALCISTA/BAJISTA/NEUTRAL
    CLAVE: 1 línea — dato más relevante
    ACCIÓN: 1 línea — qué hacer o esperar

Pydantic enforza el shape exacto y los Literals; el método `to_telegram_format()`
mantiene retrocompat con el renderer existente (concatena el resultado dentro de
`get_hourly_panorama` con emoji + nombre persona ya pre-formateados).

Uso en gemini_analyzer.py:
    from models import PanoramaPersonaResponse
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=PanoramaPersonaResponse,
    )
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
    parsed: PanoramaPersonaResponse | None = resp.parsed
    if parsed is None:
        ...fallback al texto plano existente...
    text = parsed.to_telegram_format()
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class PanoramaPersonaResponse(BaseModel):
    """Respuesta estructurada de una persona en el panorama horario.

    Reemplaza el parseo manual del texto libre con formato:
        BIAS: ALCISTA
        CLAVE: dato
        ACCIÓN: qué hacer
    """

    bias: Literal["ALCISTA", "BAJISTA", "NEUTRAL"] = Field(
        default="NEUTRAL",
        description="Sesgo direccional de la persona para la próxima hora",
    )
    clave: str = Field(
        default="—",
        max_length=200,
        description="Dato más relevante ahora mismo en 1 línea (≤200 chars)",
    )
    accion: str = Field(
        default="—",
        max_length=200,
        description="Qué hacer o esperar en la próxima hora en 1 línea (≤200 chars)",
    )

    @field_validator("bias", mode="before")
    @classmethod
    def _normalize_bias(cls, v):
        """Acepta sinónimos comunes y variaciones de case.

        Sinónimos:
            - bull / bullish / long / alcista → ALCISTA
            - bear / bearish / short / bajista → BAJISTA
            - neutral / lateral / range → NEUTRAL
        """
        if isinstance(v, str):
            up = v.strip().upper()
            if up in ("BULL", "BULLISH", "LONG", "ALCISTA"):
                return "ALCISTA"
            if up in ("BEAR", "BEARISH", "SHORT", "BAJISTA"):
                return "BAJISTA"
            if up in ("NEUTRAL", "LATERAL", "RANGE", "RANGO"):
                return "NEUTRAL"
        return "NEUTRAL"

    @field_validator("clave", "accion", mode="before")
    @classmethod
    def _strip_and_default(cls, v):
        """Trim whitespace + reemplaza vacíos por placeholder."""
        if v is None:
            return "—"
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else "—"
        return "—"

    def has_real_content(self) -> bool:
        """True si al menos un campo de contenido contiene texto real (no placeholder)."""
        return (self.clave and self.clave != "—") or (self.accion and self.accion != "—")

    def to_telegram_format(self) -> str:
        """Retorna el formato esperado por el renderer existente de `get_hourly_panorama`.

        Replica exactamente el shape que el prompt actual pide al modelo:
            BIAS: ALCISTA
            CLAVE: dato
            ACCIÓN: qué hacer

        Esto preserva retrocompat: el caller en gemini_analyzer.py concatena emoji + nombre persona
        antes de este bloque, sin tocar voice_compactor ni otros renderers.
        """
        return (
            f"BIAS: {self.bias}\n"
            f"CLAVE: {self.clave}\n"
            f"ACCIÓN: {self.accion}"
        )
