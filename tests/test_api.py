import pytest
from fastapi.testclient import TestClient

from figma_exporter.api import create_app
from figma_exporter.config import Settings
from tests.conftest import DEMO_FILE_KEY


@pytest.fixture
def client(test_settings, figma_transport):
    app = create_app(settings=test_settings, figma_transport=figma_transport)
    with TestClient(app) as test_client:
        yield test_client


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Figma" in resp.text


def test_tree_endpoint(client):
    resp = client.post("/api/figma/tree", json={"file": DEMO_FILE_KEY})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tree"]["id"] == "0:0"
    assert body["idToPath"]["10:2"].endswith("Login Card")


def test_structured_endpoint(client):
    resp = client.post(
        "/api/figma/export/structured",
        json={"file": DEMO_FILE_KEY, "node_ids": ["10-2"], "normalize": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["container"] == {"width": 320, "height": 360}
    assert 'data-figma-id="10:2"' in body["html"]
    assert body["json"][0]["id"] == "10:2"


def test_structured_endpoint_accepts_full_url(client):
    url = f"https://www.figma.com/design/{DEMO_FILE_KEY}/Demo?node-id=10-2"
    resp = client.post("/api/figma/export/structured", json={"file": url})
    assert resp.status_code == 200
    assert resp.json()["container"] == {"width": 320, "height": 360}


def test_invalid_file_ref_returns_400(client):
    resp = client.post("/api/figma/tree", json={"file": "not a key"})
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_missing_node_ids_returns_400(client):
    resp = client.post("/api/figma/export/structured", json={"file": DEMO_FILE_KEY})
    assert resp.status_code == 400


def test_pixel_endpoint_bad_format_returns_400(client):
    resp = client.post(
        "/api/figma/export/pixel",
        json={"file": DEMO_FILE_KEY, "node_ids": ["10:2"], "format": "pdf"},
    )
    assert resp.status_code == 400


def test_too_many_ids_returns_400(test_settings, figma_transport):
    settings = test_settings.model_copy(update={"max_selected_ids": 1})
    app = create_app(settings=settings, figma_transport=figma_transport)
    with TestClient(app) as c:
        resp = c.post(
            "/api/figma/export/structured",
            json={"file": DEMO_FILE_KEY, "node_ids": ["1:1", "1:2"]},
        )
    assert resp.status_code == 400


def test_ai_endpoint_without_key_returns_503(client):
    resp = client.post(
        "/api/figma/export/ai",
        json={"file": DEMO_FILE_KEY, "node_ids": ["10:2"]},
    )
    assert resp.status_code == 503
    assert "error" in resp.json()


def test_image_endpoint_without_key_returns_503(client):
    resp = client.post(
        "/api/image/export",
        files={"image": ("ui.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert resp.status_code == 503


def test_body_limit_middleware(figma_transport):
    settings = Settings(_env_file=None, figma_token="t", request_body_limit_bytes=10)
    app = create_app(settings=settings, figma_transport=figma_transport)
    with TestClient(app) as c:
        resp = c.post("/api/figma/tree", json={"file": DEMO_FILE_KEY})
    assert resp.status_code == 413


def test_pixel_endpoint_full_flow(client):
    resp = client.post(
        "/api/figma/export/pixel",
        json={"file": DEMO_FILE_KEY, "node_ids": ["10:2"], "format": "svg"},
    )
    assert resp.status_code == 200
    assert "<svg" in resp.json()["html"]
