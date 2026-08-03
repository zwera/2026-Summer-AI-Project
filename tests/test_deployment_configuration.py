"""Task 17.3 deployment configuration and bundled-resource examples."""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

import pytest

from web.config import DeploymentSettings, load_deployment_settings
from web.server import MockWebApplication, create_application


def _request(app: MockWebApplication, path: str) -> Tuple[str, Dict[str, str], bytes]:
    captured: List[Any] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        captured.extend((status, dict(headers)))

    body = b"".join(app({
        "REQUEST_METHOD": "GET", "PATH_INFO": path, "CONTENT_TYPE": "",
        "CONTENT_LENGTH": "0", "wsgi.input": BytesIO(),
    }, start_response))
    return captured[0], captured[1], body


def test_deployment_settings_are_loaded_only_from_non_secret_environment_values() -> None:
    settings = load_deployment_settings({
        "POLICE_BOT_PUBLIC_URL": "https://demo.example.test",
        "POLICE_BOT_HOST": "0.0.0.0",
        "POLICE_BOT_PORT": "8443",
        "POLICE_BOT_HTTPS_ENABLED": "true",
        "POLICE_BOT_RUN_MODE": "production",
        "UNRELATED_API_KEY": "must-not-be-read",
    })
    assert settings == DeploymentSettings(
        public_url="https://demo.example.test", host="0.0.0.0", port=8443,
        https_enabled=True, run_mode="production",
    )
    assert "secret" not in " ".join(DeploymentSettings.__dataclass_fields__).lower()
    assert "key" not in " ".join(DeploymentSettings.__dataclass_fields__).lower()


@pytest.mark.parametrize("values", [
    {"POLICE_BOT_PORT": "0"},
    {"POLICE_BOT_PORT": "not-a-number"},
    {"POLICE_BOT_HTTPS_ENABLED": "yes"},
    {"POLICE_BOT_PUBLIC_URL": "relative/path"},
    {"POLICE_BOT_PUBLIC_URL": "http://demo.example.test", "POLICE_BOT_HTTPS_ENABLED": "true"},
])
def test_invalid_deployment_settings_are_rejected(values: Dict[str, str]) -> None:
    with pytest.raises(ValueError):
        load_deployment_settings(values)


def test_fresh_application_reloads_bundled_fixture_and_serves_static_asset() -> None:
    first = create_application()
    second = create_application()
    assert first is not second
    for application in (first, second):
        status, headers, body = _request(application, "/static/app.js")
        assert status == "200 OK"
        assert headers["Content-Type"].startswith("application/javascript")
        assert b"Same-origin" in body
        assert len(body) > 0
