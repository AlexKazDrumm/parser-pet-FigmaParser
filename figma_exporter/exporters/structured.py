from __future__ import annotations

from typing import Any

from ..css import build_html_for_subtree, node_css_block
from ..errors import UpstreamError
from ..geometry import compute_bounds, get_box
from ..tree import build_path_map, find_nodes_by_ids

# Порядок полей нужен для воспроизводимого JSON.
LIGHT_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "type",
    "absoluteBoundingBox",
    "fills",
    "strokes",
    "strokeWeight",
    "cornerRadius",
    "effects",
    "style",
    "clipsContent",
    "layoutMode",
    "itemSpacing",
    "paddingTop",
    "paddingRight",
    "paddingBottom",
    "paddingLeft",
    "primaryAxisAlignItems",
    "counterAxisAlignItems",
    "characters",
)


def copy_subtree_light(node: dict[str, Any]) -> dict[str, Any]:
    out = {k: node[k] for k in LIGHT_FIELDS if k in node}
    out["children"] = [copy_subtree_light(c) for c in node.get("children", []) or []]
    return out


def _enrich_text_characters(client: Any, file_key: str, roots: list[dict[str, Any]]) -> None:
    node_map: dict[str, dict[str, Any]] = {}
    for root in roots:
        _collect_text_nodes(root, node_map)
    missing = [nid for nid, node in node_map.items() if not node.get("characters")]
    if not missing:
        return
    data = client.get_nodes(file_key, missing)
    nodes = data.get("nodes", {}) or {}
    for nid in missing:
        doc = (nodes.get(nid) or {}).get("document") or {}
        if doc.get("type") == "TEXT" and "characters" in doc:
            node_map[nid]["characters"] = doc["characters"]


def _collect_text_nodes(node: dict[str, Any], out: dict[str, dict[str, Any]]) -> None:
    if node.get("type") == "TEXT" and node.get("id"):
        out[node["id"]] = node
    for child in node.get("children", []) or []:
        _collect_text_nodes(child, out)


def structured_export(
    file_data: dict[str, Any],
    selected_ids: list[str],
    *,
    label_full_path: bool = True,
    normalize: bool = True,
    client: Any | None = None,
    file_key: str | None = None,
) -> dict[str, Any]:
    document = file_data.get("document")
    if not document:
        raise UpstreamError("Figma response has no 'document' field.")

    id_to_path = build_path_map(document)
    selected = find_nodes_by_ids(document, selected_ids)
    if not selected:
        return {"css": "", "json": [], "html": "", "container": {"width": 0, "height": 0}}

    if client is not None and file_key:
        _enrich_text_characters(client, file_key, selected)

    json_blocks = [copy_subtree_light(n) for n in selected]

    offset_x = offset_y = 0
    width = height = 0
    bounds = compute_bounds(selected)
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        width = int(round(max_x - min_x))
        height = int(round(max_y - min_y))
        if normalize:
            offset_x = -int(round(min_x))
            offset_y = -int(round(min_y))

    css_parts: list[str] = [
        "\n".join(
            [
                "/* Base container for preview */",
                ".figma-export-canvas {",
                "  position: relative;",
                f"  width: {width}px;",
                f"  height: {height}px;",
                "  overflow: hidden;",
                "}",
                "",
            ]
        )
    ]

    def walk_css(
        node: dict[str, Any],
        parent_box: dict[str, float] | None,
        is_root: bool,
    ) -> None:
        box = get_box(node)
        node_id = node.get("id", "")
        label = (
            id_to_path.get(node_id, node.get("name", node_id))
            if label_full_path
            else node.get("name", node_id)
        )
        if not box:
            for child in node.get("children", []) or []:
                walk_css(child, parent_box, False)
            return

        if is_root or parent_box is None:
            left_px = int(round(box["x"] + offset_x))
            top_px = int(round(box["y"] + offset_y))
        else:
            left_px = int(round(box["x"] - parent_box["x"]))
            top_px = int(round(box["y"] - parent_box["y"]))

        css_parts.append(
            node_css_block(
                node,
                label,
                left_px,
                top_px,
                int(round(box["width"])),
                int(round(box["height"])),
            )
        )
        for child in node.get("children", []) or []:
            walk_css(child, box, False)

    for root in selected:
        walk_css(root, None, True)

    html_body = "\n".join(build_html_for_subtree(n, id_to_path, label_full_path) for n in selected)

    return {
        "css": "\n".join(css_parts),
        "json": json_blocks,
        "html": html_body,
        "container": {"width": width, "height": height},
    }
