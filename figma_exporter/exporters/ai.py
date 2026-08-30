from __future__ import annotations

import base64
import json
import re
from typing import Any

from ..css import RENDERABLE_TYPES
from ..errors import FeatureUnavailableError, UpstreamError
from ..geometry import compute_bounds, get_box
from ..tree import find_nodes_by_ids

try:  # pragma: no cover - import guard
    from openai import OpenAI
except Exception:  # noqa: BLE001 - any import failure means the feature is off
    OpenAI = None  # type: ignore[assignment]

SINGLE_TEXT_SOFT_LIMIT = 8_000_000


def ai_available() -> bool:
    return OpenAI is not None


def build_flat_list(
    roots: list[dict[str, Any]], *, normalize: bool = True
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    bounds = compute_bounds(roots)
    off_x = off_y = 0
    width = height = 0
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        width = int(round(max_x - min_x))
        height = int(round(max_y - min_y))
        if normalize:
            off_x = -int(round(min_x))
            off_y = -int(round(min_y))

    flat: list[dict[str, Any]] = []

    def walk(
        node: dict[str, Any],
        parent: dict[str, Any] | None,
        parent_box: dict[str, float] | None,
    ) -> None:
        if node.get("type") not in RENDERABLE_TYPES:
            box = get_box(node)
            for child in node.get("children", []) or []:
                walk(child, node, box or parent_box)
            return
        box = get_box(node)
        if not box:
            for child in node.get("children", []) or []:
                walk(child, node, parent_box)
            return
        if parent_box is None:
            left = int(round(box["x"] + off_x))
            top = int(round(box["y"] + off_y))
        else:
            left = int(round(box["x"] - parent_box["x"]))
            top = int(round(box["y"] - parent_box["y"]))
        item: dict[str, Any] = {
            "id": node.get("id"),
            "name": node.get("name"),
            "type": node.get("type"),
            "parentId": parent.get("id") if parent else None,
            "left": left,
            "top": top,
            "width": int(round(box["width"])),
            "height": int(round(box["height"])),
        }
        if node.get("type") == "TEXT":
            text = node.get("characters")
            if isinstance(text, str) and text:
                item["text"] = text
        if node.get("clipsContent"):
            item["clipsContent"] = True
        flat.append(item)
        for child in node.get("children", []) or []:
            walk(child, node, box)

    for root in roots:
        walk(root, None, None)
    return flat, {"width": width, "height": height}


def _truncate_text(flat: list[dict[str, Any]], max_chars: int) -> None:
    if max_chars <= 0:
        return
    for item in flat:
        text = item.get("text")
        if isinstance(text, str) and len(text) > max_chars:
            item["text"] = text[:max_chars] + "…"


def _chunk_text(text: str, size: int = SINGLE_TEXT_SOFT_LIMIT) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _composite_pngs(
    client: Any, file_key: str, roots: list[dict[str, Any]], limit: int
) -> list[str]:
    ids = [n["id"] for n in roots if n.get("id")]
    if not ids:
        return []
    url_map = client.get_image_urls(file_key, ids, fmt="png", scale=1.0)
    out: list[str] = []
    for node_id in ids:
        url = url_map.get(node_id)
        if not url:
            continue
        try:
            data = client.download(url)
        except UpstreamError:
            continue
        out.append("data:image/png;base64," + base64.b64encode(data).decode("ascii"))
        if len(out) >= limit:
            break
    return out


def _extract_ids_from_html(text: str) -> set[str]:
    return set(re.findall(r'data-figma-id="([^"]+)"', text or ""))


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text).strip()


def _first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _html_css_from_text(text: str) -> dict[str, str] | None:
    if not text:
        return None
    text = _strip_code_fences(text)
    for candidate in (text, _first_json_object(text) or ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict) and "html" in data and "css" in data:
            return {"html": str(data["html"]), "css": str(data["css"])}
    return None


def _response_text(resp: Any) -> str:
    text = getattr(resp, "output_text", None)
    if text:
        return text
    parts: list[str] = []
    for item in getattr(resp, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) in {"output_text", "text"}:
                value = getattr(content, "text", None)
                if value:
                    parts.append(value)
    return "\n".join(parts)


def _call_model(
    client: Any,
    model: str,
    system_prompt: str,
    content_items: list[dict[str, Any]],
    max_output_tokens: int,
) -> dict[str, str]:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": content_items},
        ],
        temperature=0,
        max_output_tokens=max_output_tokens,
    )
    return _html_css_from_text(_response_text(resp)) or {}


_SYSTEM_PROMPT = (
    "You are a senior frontend engineer. You receive a compact JSON payload describing a "
    "Figma subtree (container size and a flat list of nodes with parentId and relative "
    "box) plus one or more PNG composites. Produce faithful HTML and CSS that reflect the "
    "hierarchy and relative positioning. Every node MUST have an element with "
    'data-figma-id="<ID>". Use absolute positioning with left/top/width/height; add '
    "overflow:hidden for clipsContent; insert text for TEXT nodes. Return exactly one JSON "
    'object: {"html": string, "css": string} with no markdown or commentary.'
)


def ai_export(
    file_data: dict[str, Any],
    selected_ids: list[str],
    *,
    client: Any,
    file_key: str,
    openai_api_key: str | None,
    model: str = "gpt-4o",
    normalize: bool = True,
    max_images: int = 3,
    max_text_chars_per_node: int = 4000,
    max_output_tokens: int = 8192,
) -> dict[str, Any]:
    if OpenAI is None:
        raise FeatureUnavailableError(
            "The 'openai' package is not installed (pip install -r requirements-ai.txt)."
        )
    if not openai_api_key:
        raise FeatureUnavailableError("OPENAI_API_KEY is not configured.")

    document = file_data.get("document")
    if not document:
        raise UpstreamError("Figma response has no 'document' field.")
    selected = find_nodes_by_ids(document, selected_ids)
    if not selected:
        return {"html": "", "css": "", "container": {"width": 0, "height": 0}}

    flat, container = build_flat_list(selected, normalize=normalize)
    _truncate_text(flat, max_text_chars_per_node)
    required_ids = [item["id"] for item in flat if item.get("id")]

    composites = _composite_pngs(client, file_key, selected, max(1, min(3, max_images)))

    payload = json.dumps(
        {"container": container, "nodes": flat, "requiredIds": required_ids},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chunks = _chunk_text(payload)
    content_items: list[dict[str, Any]] = [
        {"type": "input_text", "text": "Reconstruct the payload from its chunks."}
    ]
    for i, chunk in enumerate(chunks, 1):
        content_items.append({"type": "input_text", "text": f"CHUNK {i}/{len(chunks)}:\n{chunk}"})
    for data_url in composites:
        content_items.append({"type": "input_image", "image_url": data_url})

    openai_client = OpenAI(api_key=openai_api_key)
    data = _call_model(openai_client, model, _SYSTEM_PROMPT, content_items, max_output_tokens)
    if not data:
        raise UpstreamError("The model did not return a valid {html, css} object.")

    missing = [i for i in required_ids if i not in _extract_ids_from_html(data["html"])]
    result: dict[str, Any] = {
        "html": data["html"],
        "css": data["css"],
        "container": container,
    }
    if missing:
        result["warning"] = {"missingIds": missing}
    return result
