"""Regenerate the committed demo export from ``demo_figma_file.json``.

Usage:  python examples/render_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from figma_exporter.exporters.structured import structured_export

HERE = Path(__file__).resolve().parent
DEMO_FILE_KEY = "DemoLoginCard01"
DEMO_NODE_IDS = ["10:2"]


def build() -> dict:
    file_data = json.loads((HERE / "demo_figma_file.json").read_text(encoding="utf-8"))
    return structured_export(
        file_data,
        DEMO_NODE_IDS,
        label_full_path=True,
        normalize=True,
    )


def _write(name: str, text: str) -> None:
    (HERE / name).write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    result = build()
    _write("demo_output.css", result["css"] + "\n")
    _write("demo_output.html", result["html"] + "\n")
    _write("demo_output.json", json.dumps(result["json"], ensure_ascii=False, indent=2) + "\n")
    _write("demo_preview.html", _preview(result))
    print("wrote demo_output.css / demo_output.html / demo_output.json / demo_preview.html")


def _preview(result: dict) -> str:
    c = result["container"]
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8" />\n'
        "<title>Demo export preview</title>\n<style>\n"
        "body { margin: 0; padding: 40px; background: #0f172a; }\n"
        f"{result['css']}\n</style>\n</head>\n<body>\n"
        f'<div class="figma-export-canvas" style="width:{c["width"]}px;height:{c["height"]}px;'
        'margin:0 auto;">\n'
        f"{result['html']}\n</div>\n</body>\n</html>\n"
    )


if __name__ == "__main__":
    main()
