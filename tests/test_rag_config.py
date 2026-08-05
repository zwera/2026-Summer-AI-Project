"""rag.config(환경변수 로딩)에 대한 단위 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.config import MissingApiKeyError, load_settings


def test_load_settings_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        load_settings(require_api_key=True)


def test_load_settings_allows_missing_api_key_when_not_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = load_settings(require_api_key=False)
    assert settings.gemini_api_key == ""


def test_load_settings_reads_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    settings = load_settings(require_api_key=True)
    assert settings.gemini_api_key == "test-key-123"


def test_load_settings_uses_default_models_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.delenv("RAG_GENERATION_MODEL", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_MODEL", raising=False)
    settings = load_settings(require_api_key=True)
    assert settings.generation_model == "gemini-3.6-flash"
    assert settings.embedding_model == "gemini-embedding-001"


def test_load_settings_relative_path_env_resolves_against_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """상대 경로 환경변수는 현재 작업 디렉토리가 아니라 저장소 루트를 기준으로 해석해야 한다."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("RAG_CHROMA_PATH", "some_relative_dir")
    settings = load_settings(require_api_key=True)
    repo_root = Path(__file__).resolve().parent.parent
    assert settings.chroma_path == repo_root / "some_relative_dir"


def test_load_settings_absolute_path_env_is_used_as_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("RAG_CHROMA_PATH", str(tmp_path))
    settings = load_settings(require_api_key=True)
    assert settings.chroma_path == tmp_path
