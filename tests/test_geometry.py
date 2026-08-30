from figma_exporter.geometry import compute_bounds, get_box, iter_subtree
from figma_exporter.tree import find_nodes_by_ids


def test_get_box_returns_none_without_bounding_box():
    assert get_box({"id": "1:1"}) is None


def test_get_box_reads_floats():
    box = get_box({"absoluteBoundingBox": {"x": 1, "y": 2, "width": 3, "height": 4}})
    assert box == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}


def test_compute_bounds_over_demo_frame(demo_file_data):
    document = demo_file_data["document"]
    frame = find_nodes_by_ids(document, ["10:2"])
    bounds = compute_bounds(frame)
    assert bounds == (100.0, 80.0, 420.0, 440.0)


def test_iter_subtree_visits_all_nodes(demo_file_data):
    document = demo_file_data["document"]
    frame = find_nodes_by_ids(document, ["10:2"])[0]
    ids = {n["id"] for n in iter_subtree(frame)}
    assert ids == {"10:2", "10:3", "10:4", "10:5", "10:6", "10:7", "10:8", "10:9"}
