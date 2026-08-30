import pytest

from figma_exporter.errors import InputValidationError
from figma_exporter.urls import (
    normalize_node_id,
    parse_figma_ref,
    validate_file_key,
    validate_node_ids,
)


def test_bare_key_is_accepted():
    ref = parse_figma_ref("Ab12Cd34Ef56Gh78Ij90")
    assert ref.file_key == "Ab12Cd34Ef56Gh78Ij90"
    assert ref.node_ids == ()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.figma.com/design/abcDEF123456/My-File?node-id=12-345",
        "https://figma.com/file/abcDEF123456/My-File",
        "http://www.figma.com/board/abcDEF123456/Board?node-id=1-2&node-id=3-4",
    ],
)
def test_figma_urls_are_parsed(url):
    ref = parse_figma_ref(url)
    assert ref.file_key == "abcDEF123456"


def test_node_id_is_extracted_and_normalized():
    ref = parse_figma_ref("https://www.figma.com/design/abcDEF123456/x?node-id=12-345")
    assert ref.node_ids == ("12:345",)


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example.com/design/abcDEF123456/x",
        "https://www.figma.com/design/short/x",
        "https://www.figma.com/random/abcDEF123456/x",
        "ftp://www.figma.com/design/abcDEF123456/x",
        "not a key!!",
        "",
    ],
)
def test_invalid_references_are_rejected(value):
    with pytest.raises(InputValidationError):
        parse_figma_ref(value)


def test_validate_file_key_rejects_bad_chars():
    with pytest.raises(InputValidationError):
        validate_file_key("abc/def")


def test_normalize_node_id_forms():
    assert normalize_node_id("1-2") == "1:2"
    assert normalize_node_id("10:20") == "10:20"
    with pytest.raises(InputValidationError):
        normalize_node_id("abc")


def test_validate_node_ids_limit():
    assert validate_node_ids(["1-2", "3-4"]) == ["1:2", "3:4"]
    with pytest.raises(InputValidationError):
        validate_node_ids(["1-2", "3-4", "5-6"], limit=2)
