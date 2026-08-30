from __future__ import annotations

from collections.abc import Iterable
from typing import Any

Box = dict[str, float]


def safe_get(d: Any, key: str, default: Any = None) -> Any:
    return d.get(key, default) if isinstance(d, dict) else default


def get_box(node: dict[str, Any]) -> Box | None:
    box = safe_get(node, "absoluteBoundingBox")
    if not box:
        return None
    return {
        "x": float(safe_get(box, "x", 0) or 0),
        "y": float(safe_get(box, "y", 0) or 0),
        "width": float(safe_get(box, "width", 0) or 0),
        "height": float(safe_get(box, "height", 0) or 0),
    }


def iter_subtree(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield node
    for child in node.get("children", []) or []:
        yield from iter_subtree(child)


def compute_bounds(
    roots: Iterable[dict[str, Any]],
) -> tuple[float, float, float, float] | None:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    found = False
    for root in roots:
        for node in iter_subtree(root):
            box = get_box(node)
            if not box:
                continue
            min_x = min(min_x, box["x"])
            min_y = min(min_y, box["y"])
            max_x = max(max_x, box["x"] + box["width"])
            max_y = max(max_y, box["y"] + box["height"])
            found = True
    if not found:
        return None
    return (min_x, min_y, max_x, max_y)
