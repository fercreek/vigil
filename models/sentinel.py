"""SentinelResponse — Pydantic v2 schema para output de get_sentinel_report_compact.

Spec 005 (2026-05-26): reemplaza JSON mode + parse_sentinel_json manual.
Recomendación NotebookLM 4 Prompt 5 (Gemini Flash 2.5 mejor uso).

Uso en gemini_analyzer.py:
    from models import SentinelResponse
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SentinelResponse,
    )
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
    parsed: SentinelResponse | None = resp.parsed
    if parsed is None:
        ...fallback al parser manual...
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class SentinelVoices(BaseModel):
    """4 voces de la Cuadrilla Zenith.

    Cada voz: máx 8 palabras según el prompt. Pydantic enforza max_length=120 chars
    como safety (caracteres > 120 indica que el modelo se excedió, truncar en parse).
    """

    genesis: str = Field(default="—", max_length=120, description="Capital institucional / acumulación")
    exodo: str = Field(default="—", max_length=120, description="Narrativa / tecnología")
    salmos: str = Field(default="—", max_length=120, description="Confluencia técnica RSI/EMA/BB")
    apocalipsis: str = Field(default="—", max_length=120, description="Riesgo macro principal")


class SentinelResponse(BaseModel):
    """Respuesta completa del Sentinel Compact endpoint."""

    bias: Literal["LONG", "SHORT", "NEUTRAL"] = Field(
        default="NEUTRAL",
        description="Dirección del setup según la confluencia macro+técnica",
    )
    score: int = Field(
        default=0,
        ge=0,
        le=5,
        description="1 = tesis invalidada, 5 = setup impecable. 0 indica voz silenciada o sin convicción.",
    )
    verdict: Literal["ACUMULAR", "ESPERAR", "REDUCIR"] = Field(
        default="ESPERAR",
        description="Acción recomendada",
    )
    voices: SentinelVoices = Field(
        default_factory=SentinelVoices,
        description="Las 4 voces de la Cuadrilla Zenith",
    )
    action: str = Field(
        default="—",
        max_length=160,
        description="Qué hacer YA o esperar a qué nivel",
    )
    entry_zone: str = Field(
        default="—",
        max_length=60,
        description="Zona de entrada con precio, ej: '$540-$550'",
    )
    sl: str = Field(
        default="—",
        max_length=40,
        description="Stop loss, ej: '$518'",
    )
    tp1: str = Field(
        default="—",
        max_length=40,
        description="Primer target, ej: '$590'",
    )
    tp2: str = Field(
        default="—",
        max_length=40,
        description="Segundo target, ej: '$640'",
    )

    @field_validator("bias", mode="before")
    @classmethod
    def _normalize_bias(cls, v):
        """Acepta variaciones lowercase / sinónimos comunes."""
        if isinstance(v, str):
            up = v.strip().upper()
            # Sinónimos comunes
            if up in ("BULL", "BULLISH"):
                return "LONG"
            if up in ("BEAR", "BEARISH"):
                return "SHORT"
            if up in ("LONG", "SHORT", "NEUTRAL"):
                return up
        return "NEUTRAL"

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, v):
        if isinstance(v, str):
            up = v.strip().upper()
            if up in ("ACUMULAR", "ESPERAR", "REDUCIR"):
                return up
        return "ESPERAR"

    def has_real_voices(self) -> bool:
        """True si al menos una voz contiene contenido real (no placeholder "—")."""
        return any(
            v and v != "—"
            for v in (
                self.voices.genesis,
                self.voices.exodo,
                self.voices.salmos,
                self.voices.apocalipsis,
            )
        )

    def to_renderer_dict(self) -> dict:
        """Convierte a dict con shape compatible con voice_compactor.render_sentinel_compact.

        Mantiene retrocompatibilidad con el renderer existente sin tocarlo.
        """
        return {
            "bias": self.bias,
            "score": self.score,
            "verdict": self.verdict,
            "voices": {
                "genesis": self.voices.genesis,
                "exodo": self.voices.exodo,
                "salmos": self.voices.salmos,
                "apocalipsis": self.voices.apocalipsis,
            },
            "action": self.action,
            "entry_zone": self.entry_zone,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
        }
