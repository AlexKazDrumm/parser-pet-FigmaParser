from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_FIGMA_API_HOSTS = ("api.figma.com",)
_DEFAULT_FIGMA_IMAGE_HOSTS = (
    "figma-alpha-api.s3.us-west-2.amazonaws.com",
    "s3-alpha-sig.figma.com",
    "s3-alpha.figma.com",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    figma_token: str | None = Field(default=None, description="Figma personal access token")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key for AI features")

    figma_api_base: str = "https://api.figma.com"
    figma_api_host_allowlist: tuple[str, ...] = _DEFAULT_FIGMA_API_HOSTS
    figma_image_host_allowlist: tuple[str, ...] = _DEFAULT_FIGMA_IMAGE_HOSTS

    http_timeout_seconds: float = 20.0
    http_max_retries: int = 2
    http_retry_backoff_seconds: float = 0.5
    http_max_response_bytes: int = 25 * 1024 * 1024

    max_selected_ids: int = 200
    max_upload_bytes: int = 8 * 1024 * 1024
    request_body_limit_bytes: int = 2 * 1024 * 1024

    openai_default_model: str = "gpt-4o"
    openai_max_output_tokens: int = 8192

    host: str = "127.0.0.1"
    port: int = 8000

    @field_validator(
        "figma_api_host_allowlist",
        "figma_image_host_allowlist",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @property
    def image_hosts(self) -> frozenset[str]:
        return frozenset(self.figma_image_host_allowlist)

    @property
    def api_hosts(self) -> frozenset[str]:
        return frozenset(self.figma_api_host_allowlist)


@lru_cache
def get_settings() -> Settings:
    return Settings()
