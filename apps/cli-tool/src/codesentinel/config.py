from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "codesentinel-proxy"


@dataclass
class CliConfig:
    proxy_url: str
    proxy_token: str
    openharness_max_turns: int
    remediation_max_turns: int
    openharness_allowed_tools: str
    # BYOK overrides — when set, these take priority over proxy defaults
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None

    @property
    def effective_base_url(self) -> str:
        return self.base_url or self.proxy_url

    @property
    def effective_api_key(self) -> str:
        return self.api_key or self.proxy_token

    @property
    def effective_model(self) -> str:
        return self.model or "codesentinel-proxy"


class ConfigError(RuntimeError):
    pass


def _read_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _read_int(name: str, fallback: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc
    if value < 1:
        raise ConfigError(f"Environment variable {name} must be at least 1")
    return value


def load_config(
    load_dotenv_files: bool = True,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> CliConfig:
    if load_dotenv_files:
        package_root = Path(__file__).resolve().parents[2]
        load_dotenv(package_root / ".env")
        load_dotenv()

    byok_active = api_key is not None

    if byok_active:
        proxy_url = os.environ.get("CODESENTINEL_PROXY_URL", "").strip().rstrip("/")
        proxy_token = os.environ.get("CODESENTINEL_PROXY_TOKEN", "").strip()
    else:
        proxy_url = _read_required("CODESENTINEL_PROXY_URL").rstrip("/")
        proxy_token = _read_required("CODESENTINEL_PROXY_TOKEN")

    return CliConfig(
        proxy_url=proxy_url,
        proxy_token=proxy_token,
        openharness_max_turns=_read_int("CODESENTINEL_OPENHARNESS_MAX_TURNS", 50),
        remediation_max_turns=_read_int("CODESENTINEL_REMEDIATION_MAX_TURNS", 90),
        openharness_allowed_tools=os.environ.get(
            "CODESENTINEL_OPENHARNESS_ALLOWED_TOOLS", "python,bash,read_file,grep,glob"
        ),
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
