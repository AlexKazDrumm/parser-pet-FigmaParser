from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from figma_exporter.config import Settings

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
DEMO_FILE_KEY = "DemoLoginCard01"
DEMO_IMAGE_URL = "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/demo-10-2.svg"
DEMO_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="360"></svg>'


@pytest.fixture(scope="session")
def demo_file_data() -> dict:
    return json.loads((EXAMPLES / "demo_figma_file.json").read_text(encoding="utf-8"))


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        figma_token="test-token",
        openai_api_key=None,
        http_retry_backoff_seconds=0.0,
        http_max_retries=2,
    )


@pytest.fixture
def figma_handler(demo_file_data: dict) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.url.host == "api.figma.com" and url.endswith(f"/v1/files/{DEMO_FILE_KEY}"):
            return httpx.Response(200, json=demo_file_data)
        if "/v1/files/" in url and "/nodes" in url:
            return httpx.Response(200, json={"nodes": {}})
        if "/v1/images/" in url:
            return httpx.Response(200, json={"images": {"10:2": DEMO_IMAGE_URL}, "err": None})
        if request.url.host.endswith("amazonaws.com"):
            return httpx.Response(200, content=DEMO_SVG, headers={"content-type": "image/svg+xml"})
        return httpx.Response(404, json={"error": f"unexpected {url}"})

    return handler


@pytest.fixture
def figma_transport(figma_handler) -> httpx.MockTransport:
    return httpx.MockTransport(figma_handler)
