import httpx
import pytest

from figma_exporter.config import Settings
from figma_exporter.errors import InputValidationError, NotFoundError, UpstreamError
from figma_exporter.figma_client import FigmaClient


def make_client(handler, **overrides):
    settings = Settings(
        _env_file=None,
        figma_token="tok",
        http_retry_backoff_seconds=0.0,
        http_max_retries=2,
        **overrides,
    )
    return FigmaClient("tok", settings=settings, transport=httpx.MockTransport(handler))


def test_get_file_returns_json():
    def handler(request):
        assert request.headers["x-figma-token"] == "tok"
        return httpx.Response(200, json={"document": {"id": "0:0"}})

    with make_client(handler) as client:
        assert client.get_file("abcDEF123456")["document"]["id"] == "0:0"


def test_non_allowlisted_host_is_rejected():
    with make_client(lambda r: httpx.Response(200)) as client:
        with pytest.raises(InputValidationError):
            client.download("https://evil.example.com/asset.png")
        with pytest.raises(InputValidationError):
            client.download("http://figma-alpha-api.s3.us-west-2.amazonaws.com/x")


def test_retry_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"document": {}})

    with make_client(handler) as client:
        client.get_file("abcDEF123456")
    assert calls["n"] == 3


def test_retry_exhausted_raises_upstream():
    def handler(request):
        return httpx.Response(502, text="bad gateway")

    with make_client(handler) as client:
        with pytest.raises(UpstreamError):
            client.get_file("abcDEF123456")


def test_response_size_cap():
    def handler(request):
        return httpx.Response(200, content=b"x" * 5000)

    with make_client(handler, http_max_response_bytes=1000) as client:
        with pytest.raises(UpstreamError):
            client.get_file("abcDEF123456")


def test_404_maps_to_not_found():
    with make_client(lambda r: httpx.Response(404, json={})) as client:
        with pytest.raises(NotFoundError):
            client.get_file("abcDEF123456")


def test_timeout_maps_to_upstream():
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    with make_client(handler) as client:
        with pytest.raises(UpstreamError):
            client.get_file("abcDEF123456")


def test_image_urls_batching_and_filtering():
    seen = []

    def handler(request):
        seen.append(request.url.params["ids"])
        return httpx.Response(200, json={"images": {"1:1": "https://x/y", "1:2": None}})

    with make_client(handler) as client:
        urls = client.get_image_urls("abcDEF123456", ["1-1", "1-2"], fmt="png")
    assert urls == {"1:1": "https://x/y"}
