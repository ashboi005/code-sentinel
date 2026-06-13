from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "codesentinel-proxy"


@dataclass(frozen=True)
class CliConfig:
    proxy_url: str
    proxy_token: str
    openharness_max_turns: int
    openharness_allowed_tools: str


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


def load_config(load_dotenv_files: bool = True) -> CliConfig:
    if load_dotenv_files:
        package_root = Path(__file__).resolve().parents[2]
        load_dotenv(package_root / ".env")
        load_dotenv()

    return CliConfig(
        proxy_url=_read_required("CODESENTINEL_PROXY_URL").rstrip("/"),
        proxy_token=_read_required("CODESENTINEL_PROXY_TOKEN"),
        openharness_max_turns=_read_int("CODESENTINEL_OPENHARNESS_MAX_TURNS", 30),
        openharness_allowed_tools=os.environ.get("CODESENTINEL_OPENHARNESS_ALLOWED_TOOLS", "python,bash,read_file,grep,glob,docker__ps,docker__run,docker__stop,docker__start,docker__restart,docker__rm,docker__inspect,docker__logs,docker__exec,docker__images,docker__build,docker__pull,docker__push,docker__rmi"),
    )
