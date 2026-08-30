from __future__ import annotations

import html
import re
from typing import Any

from .geometry import safe_get

RENDERABLE_TYPES: frozenset[str] = frozenset(
    {
        "FRAME",
        "COMPONENT",
        "INSTANCE",
        "GROUP",
        "TEXT",
        "RECTANGLE",
        "ELLIPSE",
        "VECTOR",
        "LINE",
        "BOOLEAN_OPERATION",
        "POLYGON",
        "STAR",
        "SECTION",
    }
)

_JUSTIFY_MAP = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "SPACE_BETWEEN": "space-between",
}
_ALIGN_MAP = {"MIN": "flex-start", "CENTER": "center", "MAX": "flex-end"}
_TEXT_ALIGN_MAP = {
    "LEFT": "left",
    "CENTER": "center",
    "RIGHT": "right",
    "JUSTIFIED": "justify",
}


def rgb_to_css(color: dict[str, Any], alpha: float | None = None) -> str:
    r = int(round(safe_get(color, "r", 0) * 255))
    g = int(round(safe_get(color, "g", 0) * 255))
    b = int(round(safe_get(color, "b", 0) * 255))
    a = safe_get(color, "a", 1.0) if alpha is None else alpha
    if a < 1:
        return f"rgba({r},{g},{b},{a:.2f})"
    return f"#{r:02x}{g:02x}{b:02x}"


def paint_to_css(paint: dict[str, Any]) -> str:
    if not safe_get(paint, "visible", True):
        return "transparent"
    kind = safe_get(paint, "type", "")

    if kind == "SOLID":
        color = safe_get(paint, "color", {})
        return rgb_to_css(color, safe_get(paint, "opacity", safe_get(color, "a", 1)))

    if kind in ("GRADIENT_LINEAR", "GRADIENT_RADIAL"):
        stops = []
        for stop in safe_get(paint, "gradientStops", []) or []:
            color = safe_get(stop, "color", {})
            pos = safe_get(stop, "position", 0) * 100
            stops.append(f"{rgb_to_css(color, safe_get(color, 'a', 1))} {pos:.0f}%")
        joined = ", ".join(stops)
        if kind == "GRADIENT_LINEAR":
            return f"linear-gradient(90deg, {joined})"
        return f"radial-gradient(circle, {joined})"

    return "transparent"


def to_safe_class(name: str) -> str:
    s = (name or "").replace(" ", "_").replace(":", "_").replace("/", "__")
    s = re.sub(r"[^a-zA-Z0-9_\-]", "_", s)
    if re.match(r"^\d", s):
        s = "_" + s
    return s or "_node"


def auto_layout_css(node: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    layout = safe_get(node, "layoutMode")
    if layout not in ("HORIZONTAL", "VERTICAL"):
        return lines

    lines.append("  display: flex;")
    lines.append(
        "  flex-direction: row;" if layout == "HORIZONTAL" else "  flex-direction: column;"
    )
    spacing = safe_get(node, "itemSpacing")
    if isinstance(spacing, (int, float)):
        lines.append(f"  gap: {int(spacing)}px;")
    pads = [
        safe_get(node, k) for k in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft")
    ]
    if all(isinstance(p, (int, float)) for p in pads):
        pt, pr, pb, pl = (int(p) for p in pads)
        lines.append(f"  padding: {pt}px {pr}px {pb}px {pl}px;")
    align_h = safe_get(node, "primaryAxisAlignItems")
    align_v = safe_get(node, "counterAxisAlignItems")
    if align_h:
        lines.append(f"  justify-content: {_JUSTIFY_MAP.get(align_h, 'flex-start')};")
    if align_v:
        lines.append(f"  align-items: {_ALIGN_MAP.get(align_v, 'stretch')};")
    return lines


def _style_css(
    node: dict[str, Any], has_visible_fill: bool, first_fill: dict[str, Any] | None
) -> list[str]:
    style = safe_get(node, "style", {}) or {}
    lines: list[str] = []
    if not style:
        return lines
    if style.get("fontFamily"):
        lines.append(f"  font-family: {style['fontFamily']};")
    if style.get("fontSize") is not None:
        lines.append(f"  font-size: {int(style['fontSize'])}px;")
    if style.get("fontWeight") is not None:
        lines.append(f"  font-weight: {int(style['fontWeight'])};")
    if style.get("textAlignHorizontal"):
        lines.append(f"  text-align: {_TEXT_ALIGN_MAP.get(style['textAlignHorizontal'], 'left')};")
    if style.get("lineHeightPx") is not None:
        lines.append(f"  line-height: {float(style['lineHeightPx']):.0f}px;")
    if style.get("letterSpacing") is not None:
        lines.append(f"  letter-spacing: {float(style['letterSpacing']):.2f}px;")
    if node.get("type") == "TEXT":
        if has_visible_fill and first_fill is not None:
            lines.append(f"  color: {paint_to_css(first_fill)};")
        lines.append("  white-space: pre-wrap;")
    return lines


def node_css_block(
    node: dict[str, Any],
    label_for_css: str,
    left_px: int,
    top_px: int,
    width_px: int,
    height_px: int,
) -> str:
    css_class = to_safe_class(label_for_css)
    lines: list[str] = [
        f"/* {label_for_css} ({node.get('id')}) */",
        f".{css_class} {{",
        "  position: absolute;",
        f"  left: {left_px}px;",
        f"  top: {top_px}px;",
        f"  width: {width_px}px;",
        f"  height: {height_px}px;",
    ]

    if safe_get(node, "clipsContent", False):
        lines.append("  overflow: hidden;")

    fills = [p for p in (safe_get(node, "fills", []) or []) if safe_get(p, "visible", True)]
    first_fill = fills[0] if fills else None
    is_text = node.get("type") == "TEXT"
    if first_fill is not None and not is_text:
        lines.append(f"  background: {paint_to_css(first_fill)};")

    strokes = [s for s in (safe_get(node, "strokes", []) or []) if safe_get(s, "visible", True)]
    stroke_weight = safe_get(node, "strokeWeight")
    if strokes and stroke_weight:
        color = safe_get(strokes[0], "color")
        if color:
            lines.append(f"  border: {int(stroke_weight)}px solid {rgb_to_css(color)};")

    corner_radius = safe_get(node, "cornerRadius")
    if isinstance(corner_radius, (int, float)):
        lines.append(f"  border-radius: {int(corner_radius)}px;")

    shadows: list[str] = []
    for effect in safe_get(node, "effects", []) or []:
        if not safe_get(effect, "visible", True):
            continue
        if safe_get(effect, "type") not in ("DROP_SHADOW", "INNER_SHADOW"):
            continue
        color = safe_get(effect, "color", {})
        offset = safe_get(effect, "offset", {"x": 0, "y": 0})
        radius = int(safe_get(effect, "radius", 0))
        x = int(safe_get(offset, "x", 0))
        y = int(safe_get(offset, "y", 0))
        inset = " inset" if safe_get(effect, "type") == "INNER_SHADOW" else ""
        shadows.append(
            f"{x}px {y}px {radius}px {rgb_to_css(color, safe_get(color, 'a', 1))}{inset}"
        )
    if shadows:
        lines.append(f"  box-shadow: {', '.join(shadows)};")

    lines.extend(_style_css(node, first_fill is not None, first_fill))
    lines.extend(auto_layout_css(node))
    lines.append("}\n")
    return "\n".join(lines)


def build_html_for_subtree(
    node: dict[str, Any],
    id_to_path: dict[str, str],
    label_full_path: bool,
) -> str:
    node_id = node.get("id", "")
    label = (
        id_to_path.get(node_id, node.get("name", node_id))
        if label_full_path
        else node.get("name", node_id)
    )
    css_class = to_safe_class(label)
    parts: list[str] = []

    if node.get("type") == "TEXT":
        text = node.get("characters", "")
        if isinstance(text, str) and text:
            parts.append(html.escape(text, quote=False))

    for child in node.get("children", []) or []:
        parts.append(build_html_for_subtree(child, id_to_path, label_full_path))

    return f'<div class="{css_class}" data-figma-id="{html.escape(node_id)}">{"".join(parts)}</div>'
