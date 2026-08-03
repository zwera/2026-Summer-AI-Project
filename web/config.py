"""Environment-only deployment settings for the bundled mock web application.

No credentials, API keys, tokens, or external service settings are accepted because
this demonstration runs solely from its bundled fixtures and static assets.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True)
class DeploymentSettings:
    """Non-secret values supplied by the hosting environment."""

    public_url: str
    host: str
    port: int
    https_enabled: bool
    run_mode: str


_DEFAULT_PUBLIC_URL = "http://127.0.0.1:8000"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000
_ALLOWED_RUN_MODES = frozenset({"development", "production", "test"})


def load_deployment_settings(environ: Mapping[str, str] | None = None) -> DeploymentSettings:
    """Read and validate deployment settings without reading any secret values."""
    values = os.environ if environ is None else environ
    host = values.get("POLICE_BOT_HOST", _DEFAULT_HOST).strip()
    public_url = values.get("POLICE_BOT_PUBLIC_URL", _DEFAULT_PUBLIC_URL).strip().rstrip("/")
    run_mode = values.get("POLICE_BOT_RUN_MODE", "production").strip().lower()

    if not host:
        raise ValueError("POLICE_BOT_HOST must not be empty")
    if run_mode not in _ALLOWED_RUN_MODES:
        raise ValueError("POLICE_BOT_RUN_MODE must be development, production, or test")

    try:
        port = int(values.get("POLICE_BOT_PORT", str(_DEFAULT_PORT)))
    except ValueError as error:
        raise ValueError("POLICE_BOT_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("POLICE_BOT_PORT must be between 1 and 65535")

    parsed = urlparse(public_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("POLICE_BOT_PUBLIC_URL must be an absolute HTTP(S) URL")

    raw_https = values.get("POLICE_BOT_HTTPS_ENABLED", "true" if parsed.scheme == "https" else "false")
    normalized_https = raw_https.strip().lower()
    if normalized_https not in {"true", "false"}:
        raise ValueError("POLICE_BOT_HTTPS_ENABLED must be true or false")
    https_enabled = normalized_https == "true"
    if https_enabled and parsed.scheme != "https":
        raise ValueError("HTTPS-enabled deployments require an HTTPS public URL")

    return DeploymentSettings(
        public_url=public_url,
        host=host,
        port=port,
        https_enabled=https_enabled,
        run_mode=run_mode,
    )
