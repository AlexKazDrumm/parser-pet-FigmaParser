import pytest

from figma_exporter.errors import FeatureUnavailableError, InputValidationError
from figma_exporter.exporters import ai, image


def test_build_flat_list_relative_positions(demo_file_data):
    from figma_exporter.tree import find_nodes_by_ids

    frame = find_nodes_by_ids(demo_file_data["document"], ["10:2"])
    flat, container = ai.build_flat_list(frame, normalize=True)
    assert container == {"width": 320, "height": 360}
    by_id = {item["id"]: item for item in flat}
    assert by_id["10:2"]["left"] == 0 and by_id["10:2"]["top"] == 0
    # Title is positioned relative to its parent frame.
    assert by_id["10:3"]["left"] == 24 and by_id["10:3"]["top"] == 24
    assert by_id["10:3"]["text"] == "Sign in"
    assert by_id["10:3"]["parentId"] == "10:2"


def test_html_css_from_text_parses_fenced_json():
    parsed = ai._html_css_from_text('```json\n{"html": "<div></div>", "css": ".a{}"}\n```')
    assert parsed == {"html": "<div></div>", "css": ".a{}"}


def test_html_css_from_text_extracts_embedded_object():
    parsed = ai._html_css_from_text('noise {"html": "<b></b>", "css": ""} trailing')
    assert parsed == {"html": "<b></b>", "css": ""}


def test_html_css_from_text_rejects_non_matching():
    assert ai._html_css_from_text("just prose") is None


def test_extract_ids_from_html():
    assert ai._extract_ids_from_html('<div data-figma-id="1:2"></div>') == {"1:2"}


def test_ai_export_without_dependency_or_key(demo_file_data, monkeypatch):
    monkeypatch.setattr(ai, "OpenAI", None)
    with pytest.raises(FeatureUnavailableError):
        ai.ai_export(
            demo_file_data,
            ["10:2"],
            client=None,
            file_key="DemoLoginCard01",
            openai_api_key=None,
        )


def test_bad_css_units_detection():
    assert image._bad_css_units("width: 50%;")
    assert image._bad_css_units("height: calc(100px - 2px);")
    assert not image._bad_css_units("width: 320px; height: 44px;")


def test_image_export_requires_key(monkeypatch):
    monkeypatch.setattr(image, "OpenAI", object)  # dependency "present"
    with pytest.raises(FeatureUnavailableError):
        image.image_export(b"data", "image/png", openai_api_key=None)


def test_image_export_rejects_unknown_mime(monkeypatch):
    monkeypatch.setattr(image, "OpenAI", object)
    with pytest.raises(InputValidationError):
        image.image_export(b"data", "application/pdf", openai_api_key="k")


def test_image_allowed_mimes():
    assert "image/png" in image.ALLOWED_IMAGE_MIMES
    assert "image/svg+xml" not in image.ALLOWED_IMAGE_MIMES
