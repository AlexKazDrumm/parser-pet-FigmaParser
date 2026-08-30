"""Pixel-perfect export: compose Figma-rendered node images into absolute HTML."""

from __future__ import annotations

import base64
import html
import re
from typing import Any

from ..errors import InputValidationError, UpstreamError
from ..geometry import compute_bounds, get_box
from ..tree import find_nodes_by_ids

_XML_DECL_RE = re.compile(r"<\?xml.*?\?>", re.DOTALL)
_DOCTYPE_RE = re.compile(r"<!DOCTYPE.*?>", re.DOTALL)
_ALLOWED_FORMATS = {"svg", "png"}


def _clean_svg(text: str) -> str:
    text = _XML_DECL_RE.sub("", text).strip()
    text = _DOCTYPE_RE.sub("", text).strip()
    return text


def pixel_export(
    file_data: dict[str, Any],
    selected_ids: list[str],
    *,
    client: Any,
    file_key: str,
    fmt: str = "svg",
    scale: float = 1.0,
    normalize: bool = True,
) -> dict[str, Any]:
    fmt = (fmt or "svg").lower().strip()
    if fmt not in _ALLOWED_FORMATS:
        raise InputValidationError("format must be 'svg' or 'png'.")
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        scale = 1.0
    if scale <= 0:
        scale = 1.0

    document = file_data.get("document")
    if not document:
        raise UpstreamError("Figma response has no 'document' field.")

    selected = find_nodes_by_ids(document, selected_ids)
    if not selected:
        return {"html": "", "container": {"width": 0, "height": 0}, "url_map": {}}

    bounds = compute_bounds(selected)
    if not bounds:
        return {"html": "", "container": {"width": 0, "height": 0}, "url_map": {}}
    min_x, min_y, max_x, max_y = bounds
    width = int(round(max_x - min_x))
    height = int(round(max_y - min_y))
    off_x = -int(round(min_x)) if normalize else 0
    off_y = -int(round(min_y)) if normalize else 0

    ids = [n["id"] for n in selected if n.get("id")]
    url_map = client.get_image_urls(file_key, ids, fmt=fmt, scale=scale, use_absolute_bounds=True)

    pieces: list[str] = []
    for node in selected:
        node_id = node.get("id")
        box = get_box(node)
        url = url_map.get(node_id) if node_id else None
        if not node_id or not box or not url:
            continue
        left = int(round(box["x"] + off_x))
        top = int(round(box["y"] + off_y))
        w = int(round(box["width"]))
        h = int(round(box["height"]))
        style = f"position:absolute;left:{left}px;top:{top}px;width:{w}px;height:{h}px;"
        try:
            content = client.download(url)
        except UpstreamError:
            continue
        if fmt == "svg":
            pieces.append(
                f'<div style="{style}overflow:hidden">'
                f"{_clean_svg(content.decode('utf-8', 'replace'))}</div>"
            )
        else:
            b64 = base64.b64encode(content).decode("ascii")
            pieces.append(
                f'<img src="data:image/png;base64,{b64}" style="{style}" '
                f'alt="node {html.escape(node_id)}" />'
            )

    return {
        "html": "\n".join(pieces),
        "container": {"width": width, "height": height},
        "url_map": url_map,
    }
