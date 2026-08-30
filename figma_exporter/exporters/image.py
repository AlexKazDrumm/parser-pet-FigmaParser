from __future__ import annotations

import base64
import io
import math
import re
from typing import Any

from ..errors import FeatureUnavailableError, InputValidationError, UpstreamError
from .ai import _html_css_from_text, _response_text

try:  # pragma: no cover - import guard
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore[assignment]

try:  # pragma: no cover - import guard
    from PIL import Image, ImageChops, ImageStat
except Exception:  # noqa: BLE001
    Image = ImageChops = ImageStat = None  # type: ignore[assignment]

try:  # pragma: no cover - import guard
    from playwright.sync_api import sync_playwright
except Exception:  # noqa: BLE001
    sync_playwright = None  # type: ignore[assignment]

ALLOWED_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


def _data_url(mime: str, data: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image_size(data: bytes) -> tuple[int, int]:
    if Image is not None:
        try:
            with Image.open(io.BytesIO(data)) as im:
                return int(im.width), int(im.height)
        except Exception:  # noqa: BLE001
            pass
    return 1024, 768


def _system_prompt(width: int, height: int) -> str:
    return (
        "You are a senior frontend engineer converting a single UI screenshot into HTML+CSS.\n"
        f'Root: one <div class="figma-export-canvas"> sized exactly {width}x{height}px.\n'
        "Use absolute positioning in px only (no %, vw, vh, rem, em, calc, or transforms).\n"
        "Preserve the row/column structure, exact gaps, shapes, radii, borders, shadows.\n"
        "Sample colors from the screenshot. Approximate fonts but match size/weight/spacing.\n"
        "Do not invent elements. Return exactly one JSON object: "
        '{"html": string, "css": string} with no markdown.'
    )


def _bad_css_units(css: str) -> bool:
    if not isinstance(css, str):
        return True
    return bool(
        re.search(
            r"(?:\d\s*(?:%|vw|vh|rem|em))|calc\s*\(|transform\s*:\s*[^;]*scale",
            css,
            re.IGNORECASE,
        )
    )


def _rasterize(html_text: str, css_text: str, width: int, height: int) -> bytes | None:
    if sync_playwright is None:
        return None
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0;background:transparent}"
        f"{css_text}</style></head><body>{html_text}</body></html>"
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": width, "height": height, "deviceScaleFactor": 1}
            )
            page.set_content(document, wait_until="load")
            shot = page.screenshot(full_page=False)
            browser.close()
            return shot
    except Exception:  # noqa: BLE001
        return None


def _diff_metrics(src_png: bytes, pred_png: bytes) -> dict[str, Any]:
    if Image is None or ImageChops is None or ImageStat is None:
        return {}
    a = Image.open(io.BytesIO(src_png)).convert("RGB")
    b = Image.open(io.BytesIO(pred_png)).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / 3.0
    rmse = sum(stat.rms) / 3.0
    psnr = 20.0 * math.log10(255.0 / rmse) if rmse > 0 else float("inf")
    return {
        "mae": mae,
        "psnr": psnr,
        "render_png": _data_url("image/png", pred_png),
        "diff_png": _data_url("image/png", _png_bytes(diff.convert("RGBA"))),
    }


def image_export(
    data: bytes,
    content_type: str,
    *,
    openai_api_key: str | None,
    model: str = "gpt-4o",
    max_output_tokens: int = 8192,
) -> dict[str, Any]:
    if OpenAI is None:
        raise FeatureUnavailableError(
            "The 'openai' package is not installed (pip install -r requirements-ai.txt)."
        )
    if not openai_api_key:
        raise FeatureUnavailableError("OPENAI_API_KEY is not configured.")
    if content_type not in ALLOWED_IMAGE_MIMES:
        raise InputValidationError(
            f"Unsupported image type {content_type!r}. Allowed: "
            + ", ".join(sorted(ALLOWED_IMAGE_MIMES))
        )
    if not data:
        raise InputValidationError("The uploaded image is empty.")

    width, height = _image_size(data)
    src_data_url = _data_url(content_type, data)
    content_items = [
        {
            "type": "input_text",
            "text": f"Container size must be exactly {width}x{height}px.",
        },
        {"type": "input_image", "image_url": src_data_url},
    ]

    openai_client = OpenAI(api_key=openai_api_key)
    resp = openai_client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": _system_prompt(width, height)}],
            },
            {"role": "user", "content": content_items},
        ],
        temperature=0,
        max_output_tokens=max_output_tokens,
    )
    parsed = _html_css_from_text(_response_text(resp))
    if not parsed:
        raise UpstreamError("The model did not return a valid {html, css} object.")
    html_text, css_text = parsed["html"], parsed["css"]

    result: dict[str, Any] = {
        "html": html_text,
        "css": css_text,
        "container": {"width": width, "height": height},
        "warnings": [],
    }
    if _bad_css_units(css_text):
        result["warnings"].append("CSS contains non-px units; layout may not be pixel-exact.")

    render_png = _rasterize(html_text, css_text, width, height)
    if render_png is None:
        result["warnings"].append(
            "Playwright/Chromium unavailable; skipped rasterisation and diff metrics."
        )
        return result

    if content_type.endswith("png"):
        src_png = data
    elif Image is not None:
        src_png = _png_bytes(Image.open(io.BytesIO(data)).convert("RGBA"))
    else:  # pragma: no cover - Image guaranteed by the guard above
        src_png = data
    result["debug"] = _diff_metrics(src_png, render_png)
    return result
