import importlib

from figma_exporter.exporters.structured import structured_export
from figma_exporter.tree import build_relative_path_map, simplify_tree


def test_simplify_tree_shape(demo_file_data):
    simple = simplify_tree(demo_file_data["document"])
    assert set(simple) == {"id", "name", "type", "children"}
    assert simple["children"][0]["type"] == "CANVAS"


def test_build_relative_path_map_multiple_roots():
    roots = [
        {"id": "a", "name": "A", "children": [{"id": "a1", "name": "child"}]},
        {"id": "b", "name": "B"},
    ]
    paths = build_relative_path_map(roots)
    assert paths == {"a": "A", "a1": "A/child", "b": "B"}


class _EnrichClient:
    def __init__(self):
        self.calls = []

    def get_nodes(self, file_key, ids):
        self.calls.append(list(ids))
        return {"nodes": {ids[0]: {"document": {"type": "TEXT", "characters": "Recovered"}}}}


def test_structured_export_enriches_missing_text():
    file_data = {
        "document": {
            "id": "0:0",
            "name": "Doc",
            "children": [
                {
                    "id": "1:1",
                    "name": "Frame",
                    "type": "FRAME",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 10, "height": 10},
                    "children": [
                        {
                            "id": "1:2",
                            "name": "T",
                            "type": "TEXT",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 10, "height": 4},
                        }
                    ],
                }
            ],
        }
    }
    client = _EnrichClient()
    result = structured_export(file_data, ["1:1"], client=client, file_key="abcDEF123456")
    assert client.calls == [["1:2"]]
    assert "Recovered" in result["html"]


def test_package_entrypoint_importable():
    module = importlib.import_module("figma_exporter.__main__")
    assert callable(module.main)
