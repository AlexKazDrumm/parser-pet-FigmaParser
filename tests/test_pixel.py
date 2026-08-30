import pytest

from figma_exporter.errors import InputValidationError
from figma_exporter.exporters.pixel import pixel_export


class FakeClient:
    def __init__(self, urls, blobs):
        self._urls = urls
        self._blobs = blobs
        self.downloaded = []

    def get_image_urls(self, file_key, ids, **kwargs):
        return {i: self._urls[i] for i in ids if i in self._urls}

    def download(self, url):
        self.downloaded.append(url)
        return self._blobs[url]


def test_pixel_export_svg_composition(demo_file_data):
    client = FakeClient(
        urls={"10:2": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/a.svg"},
        blobs={
            "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/a.svg": (
                b'<?xml version="1.0"?><svg width="320" height="360"></svg>'
            )
        },
    )
    result = pixel_export(
        demo_file_data, ["10:2"], client=client, file_key="DemoLoginCard01", fmt="svg"
    )
    assert result["container"] == {"width": 320, "height": 360}
    assert "position:absolute;left:0px;top:0px;width:320px;height:360px;" in result["html"]
    assert '<svg width="320"' in result["html"]
    assert "<?xml" not in result["html"]


def test_pixel_export_png_data_uri(demo_file_data):
    client = FakeClient(
        urls={"10:2": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/a.png"},
        blobs={
            "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/a.png": b"\x89PNG\r\n\x1a\n"
        },
    )
    result = pixel_export(
        demo_file_data, ["10:2"], client=client, file_key="DemoLoginCard01", fmt="png"
    )
    assert 'src="data:image/png;base64,' in result["html"]


def test_pixel_export_rejects_bad_format(demo_file_data):
    with pytest.raises(InputValidationError):
        pixel_export(demo_file_data, ["10:2"], client=FakeClient({}, {}), file_key="x", fmt="pdf")


def test_pixel_export_unknown_ids_returns_empty(demo_file_data):
    result = pixel_export(
        demo_file_data, ["99:99"], client=FakeClient({}, {}), file_key="DemoLoginCard01"
    )
    assert result["html"] == ""
    assert result["container"] == {"width": 0, "height": 0}
