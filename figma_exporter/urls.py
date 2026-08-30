from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from .errors import InputValidationError

FILE_KEY_RE = re.compile(r"^[A-Za-z0-9]{10,64}$")
NODE_ID_RE = re.compile(r"^[0-9]+[:-][0-9]+$")

_ALLOWED_FIGMA_HOSTS = {"figma.com", "www.figma.com"}
_ALLOWED_PATH_PREFIXES = {"file", "design", "proto", "board"}


@dataclass(frozen=True)
class FigmaRef:
    file_key: str
    node_ids: tuple[str, ...] = field(default_factory=tuple)


def validate_file_key(value: str) -> str:
    key = (value or "").strip()
    if not FILE_KEY_RE.match(key):
        raise InputValidationError("File key must be 10-64 alphanumeric characters.")
    return key


def normalize_node_id(value: str) -> str:
    raw = (value or "").strip()
    if not NODE_ID_RE.match(raw):
        raise InputValidationError(f"Node id {value!r} is not in the form '123:456' or '123-456'.")
    return raw.replace("-", ":")


def validate_node_ids(values: object, *, limit: int | None = None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    try:
        items = list(values)  # type: ignore[arg-type]
    except TypeError as exc:  # pragma: no cover - defensive
        raise InputValidationError("node_ids must be a list of strings.") from exc
    if limit is not None and len(items) > limit:
        raise InputValidationError(f"Too many node ids: {len(items)} (limit {limit}).")
    return [normalize_node_id(str(item)) for item in items]


def _parse_url(value: str) -> FigmaRef:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise InputValidationError("Only http(s) Figma URLs are accepted.")
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_FIGMA_HOSTS:
        raise InputValidationError(f"Host {host!r} is not a Figma host.")

    segments = [seg for seg in parsed.path.split("/") if seg]
    if len(segments) < 2 or segments[0] not in _ALLOWED_PATH_PREFIXES:
        raise InputValidationError(
            "Figma URL must look like https://www.figma.com/design/<key>/<name>."
        )
    file_key = validate_file_key(segments[1])

    node_ids: list[str] = []
    query = parse_qs(parsed.query)
    for raw in query.get("node-id", []):
        node_ids.append(normalize_node_id(raw))
    return FigmaRef(file_key=file_key, node_ids=tuple(node_ids))


def parse_figma_ref(value: str) -> FigmaRef:
    text = (value or "").strip()
    if not text:
        raise InputValidationError("Empty Figma reference.")
    if "://" in text or text.lower().startswith("www."):
        if text.lower().startswith("www."):
            text = "https://" + text
        return _parse_url(text)
    return FigmaRef(file_key=validate_file_key(text))
