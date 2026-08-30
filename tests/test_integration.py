from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from figma_exporter.api import create_app
from tests.conftest import DEMO_FILE_KEY

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_full_structured_export_flow(test_settings, figma_transport):
    app = create_app(settings=test_settings, figma_transport=figma_transport)
    with TestClient(app) as client:
        tree = client.post("/api/figma/tree", json={"file": DEMO_FILE_KEY}).json()
        target = tree["idToPath"]
        assert "10:2" in target

        resp = client.post(
            "/api/figma/export/structured",
            json={"file": DEMO_FILE_KEY, "node_ids": ["10:2"], "label_full_path": True},
        )
        assert resp.status_code == 200
        body = resp.json()

    assert body["css"] + "\n" == (EXAMPLES / "demo_output.css").read_text(encoding="utf-8")
    assert body["html"] + "\n" == (EXAMPLES / "demo_output.html").read_text(encoding="utf-8")
    assert body["json"] == json.loads((EXAMPLES / "demo_output.json").read_text(encoding="utf-8"))
