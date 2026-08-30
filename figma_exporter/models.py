from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .errors import InputValidationError
from .urls import parse_figma_ref, validate_node_ids

# Жёсткий предел для первичной проверки тела запроса.
_HARD_ID_CEILING = 2000


def _as_value_error(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except InputValidationError as exc:
        raise ValueError(str(exc)) from exc


class _FigmaRequest(BaseModel):
    file: str = Field(..., description="Figma file URL or bare file key")
    token: str | None = Field(default=None, description="Figma token; falls back to FIGMA_TOKEN")

    @field_validator("file")
    @classmethod
    def _validate_file(cls, value: str) -> str:
        _as_value_error(parse_figma_ref, value)
        return value.strip()

    @property
    def file_key(self) -> str:
        return parse_figma_ref(self.file).file_key

    @property
    def url_node_ids(self) -> tuple[str, ...]:
        return parse_figma_ref(self.file).node_ids


class TreeRequest(_FigmaRequest):
    pass


class _SelectionRequest(_FigmaRequest):
    node_ids: list[str] = Field(default_factory=list)
    normalize: bool = True

    @model_validator(mode="after")
    def _resolve_ids(self) -> _SelectionRequest:
        combined = list(self.url_node_ids) + list(self.node_ids)
        normalized = _as_value_error(validate_node_ids, combined, limit=_HARD_ID_CEILING)
        if not normalized:
            raise ValueError("Provide at least one node id (in node_ids or the URL's node-id).")
        self.node_ids = normalized
        return self


class StructuredExportRequest(_SelectionRequest):
    label_full_path: bool = True


class PixelExportRequest(_SelectionRequest):
    format: str = "svg"
    scale: float = Field(default=1.0, gt=0, le=4)

    @field_validator("format")
    @classmethod
    def _fmt(cls, value: str) -> str:
        value = (value or "").lower().strip()
        if value not in {"svg", "png"}:
            raise ValueError("format must be 'svg' or 'png'.")
        return value


class AIExportRequest(_SelectionRequest):
    model: str | None = None
    max_images: int = Field(default=3, ge=1, le=3)
    max_text_chars_per_node: int = Field(default=4000, ge=0, le=20000)


class ErrorResponse(BaseModel):
    error: str
