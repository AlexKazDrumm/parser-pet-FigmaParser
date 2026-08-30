import json
from pathlib import Path

from figma_exporter.exporters.structured import LIGHT_FIELDS, copy_subtree_light, structured_export

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_structured_export_matches_committed_demo(demo_file_data):
    result = structured_export(demo_file_data, ["10:2"], label_full_path=True, normalize=True)
    assert result["css"] + "\n" == (EXAMPLES / "demo_output.css").read_text(encoding="utf-8")
    assert result["html"] + "\n" == (EXAMPLES / "demo_output.html").read_text(encoding="utf-8")
    serialized = json.dumps(result["json"], ensure_ascii=False, indent=2) + "\n"
    assert serialized == (EXAMPLES / "demo_output.json").read_text(encoding="utf-8")


def test_light_json_key_order_is_deterministic(demo_file_data):
    node = {
        "characters": "x",
        "id": "1:1",
        "type": "TEXT",
        "name": "n",
        "extra": "dropped",
    }
    light = copy_subtree_light(node)
    assert list(light) == ["id", "name", "type", "characters", "children"]
    assert "extra" not in light
    # The declared field order is what the export emits.
    assert [f for f in LIGHT_FIELDS if f in node] == ["id", "name", "type", "characters"]


def test_structured_export_container_and_normalization(demo_file_data):
    result = structured_export(demo_file_data, ["10:2"], normalize=True)
    assert result["container"] == {"width": 320, "height": 360}
    assert ".figma-export-canvas" in result["css"]
    assert 'data-figma-id="10:2"' in result["html"]
    # The root frame is normalized to the origin.
    assert "left: 0px;" in result["css"]


def test_structured_export_without_normalization_keeps_absolute_origin(demo_file_data):
    result = structured_export(demo_file_data, ["10:2"], normalize=False)
    assert "left: 100px;" in result["css"]
    assert "top: 80px;" in result["css"]


def test_structured_export_unknown_ids_returns_empty(demo_file_data):
    result = structured_export(demo_file_data, ["99:99"])
    assert result == {"css": "", "json": [], "html": "", "container": {"width": 0, "height": 0}}
