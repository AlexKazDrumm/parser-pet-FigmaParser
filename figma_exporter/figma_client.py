from __future__ import annotations

import json
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Settings, get_settings
from .errors import ConfigurationError, InputValidationError, NotFoundError, UpstreamError
from .urls import validate_file_key, validate_node_ids

_RETRY_STATUS = {429, 500, 502, 503, 504}
_NODE_BATCH = 80


def _image_host_allowed(host: str, allowlist: Iterable[str]) -> bool:
    host = host.lower()
    if host in {h.lower() for h in allowlist}:
        return True
    return host.endswith(".amazonaws.com") and "figma" in host


class FigmaClient:
    def __init__(
        self,
        token: str | None,
        *,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._token = (token or "").strip()
        self._client = httpx.Client(
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "figma-exporter/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FigmaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _require_token(self) -> str:
        if not self._token:
            raise ConfigurationError(
                "Figma token is not set. Provide it in the request or via FIGMA_TOKEN."
            )
        return self._token

    def _check_host(self, url: str, allowlist: Iterable[str], *, image: bool) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise InputValidationError("Only https requests are allowed.")
        host = (parsed.hostname or "").lower()
        ok = (
            _image_host_allowed(host, allowlist)
            if image
            else host in {h.lower() for h in allowlist}
        )
        if not ok:
            raise InputValidationError(f"Host {host!r} is not on the allowlist.")

    def _read_capped(self, response: httpx.Response) -> bytes:
        cap = self.settings.http_max_response_bytes
        buffer = bytearray()
        for chunk in response.iter_bytes():
            buffer.extend(chunk)
            if len(buffer) > cap:
                raise UpstreamError(f"Figma response exceeded the {cap}-byte limit.")
        return bytes(buffer)

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        image: bool = False,
    ) -> tuple[int, bytes]:
        allowlist = (
            self.settings.figma_image_host_allowlist
            if image
            else self.settings.figma_api_host_allowlist
        )
        self._check_host(url, allowlist, image=image)

        attempts = self.settings.http_max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                with self._client.stream(method, url, params=params, headers=headers) as response:
                    if response.status_code in _RETRY_STATUS and attempt < attempts - 1:
                        response.close()
                        time.sleep(self.settings.http_retry_backoff_seconds * (attempt + 1))
                        continue
                    body = self._read_capped(response)
                    return response.status_code, body
            except httpx.TimeoutException as exc:
                last_exc = exc
            except httpx.TransportError as exc:
                last_exc = exc
            if attempt < attempts - 1:
                time.sleep(self.settings.http_retry_backoff_seconds * (attempt + 1))
        raise UpstreamError(f"Figma request failed: {last_exc}")

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        status, body = self._send(
            "GET", url, params=params, headers={"X-Figma-Token": self._require_token()}
        )
        if status == 404:
            raise NotFoundError("Figma resource not found (check the file key).")
        if status in (401, 403):
            raise UpstreamError("Figma rejected the token (401/403).")
        if status >= 400:
            snippet = body[:200].decode("utf-8", "replace")
            raise UpstreamError(f"Figma API error {status}: {snippet}")
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise UpstreamError("Figma returned a non-JSON body.") from exc
        if not isinstance(data, dict):
            raise UpstreamError("Figma returned an unexpected JSON shape.")
        return data

    def get_file(self, file_key: str) -> dict[str, Any]:
        key = validate_file_key(file_key)
        return self._get_json(f"{self.settings.figma_api_base}/v1/files/{key}")

    def get_nodes(self, file_key: str, node_ids: list[str]) -> dict[str, Any]:
        key = validate_file_key(file_key)
        ids = validate_node_ids(node_ids, limit=self.settings.max_selected_ids)
        merged: dict[str, Any] = {}
        for start in range(0, len(ids), _NODE_BATCH):
            batch = ids[start : start + _NODE_BATCH]
            data = self._get_json(
                f"{self.settings.figma_api_base}/v1/files/{key}/nodes",
                params={"ids": ",".join(batch)},
            )
            merged.update(data.get("nodes", {}) or {})
        return {"nodes": merged}

    def get_image_urls(
        self,
        file_key: str,
        node_ids: list[str],
        *,
        fmt: str = "svg",
        scale: float = 1.0,
        use_absolute_bounds: bool = True,
    ) -> dict[str, str]:
        key = validate_file_key(file_key)
        ids = validate_node_ids(node_ids, limit=self.settings.max_selected_ids)
        if not ids:
            return {}
        params: dict[str, Any] = {"ids": ",".join(ids), "format": fmt}
        if fmt.lower() != "svg" and scale:
            params["scale"] = str(scale)
        if use_absolute_bounds:
            params["use_absolute_bounds"] = "true"
        data = self._get_json(f"{self.settings.figma_api_base}/v1/images/{key}", params=params)
        if data.get("err"):
            raise UpstreamError(f"Figma image render failed: {data['err']}")
        return {k: v for k, v in (data.get("images") or {}).items() if v}

    def download(self, url: str) -> bytes:
        status, body = self._send("GET", url, image=True)
        if status >= 400:
            raise UpstreamError(f"Asset download failed with status {status}.")
        return body
