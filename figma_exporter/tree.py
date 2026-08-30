from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .geometry import iter_subtree

__all__ = [
    "simplify_tree",
    "build_path_map",
    "build_relative_path_map",
    "find_nodes_by_ids",
    "iter_subtree",
]


def simplify_tree(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "children": [simplify_tree(child) for child in node.get("children", []) or []],
    }


def _walk_paths(node: dict[str, Any], prefix: str, out: dict[str, str]) -> None:
    name = node.get("name", "")
    current = f"{prefix}/{name}" if prefix else name
    node_id = node.get("id")
    if node_id:
        out[node_id] = current
    for child in node.get("children", []) or []:
        _walk_paths(child, current, out)


def build_path_map(root: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    _walk_paths(root, "", out)
    return out


def build_relative_path_map(roots: Iterable[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for root in roots:
        _walk_paths(root, "", out)
    return out


def find_nodes_by_ids(root: dict[str, Any], ids: Iterable[str]) -> list[dict[str, Any]]:
    wanted = set(ids)
    result: list[dict[str, Any]] = []
    for node in iter_subtree(root):
        if node.get("id") in wanted:
            result.append(node)
    return result
