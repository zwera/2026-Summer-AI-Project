"""실제 RAG 파이프라인의 환경 설정.

API 키와 같은 비밀값은 소스 코드에 두지 않고 서버 측 환경변수(``GEMINI_API_KEY`` 등)
또는 저장소 루트의 ``.env`` 파일(개발용, git에 커밋하지 않음)에서만 읽는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv는 필수 의존성으로 고정되어 있음
    load_dotenv = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    """저장소 루트의 ``.env`` 파일을 최초 접근 시 한 번만 로드한다."""
    global _ENV_LOADED
    if _ENV_LOADED or load_dotenv is None:
        return
    env_path = _REPO_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    _ENV_LOADED = True


@dataclass(frozen=True)
class RagSettings:
    """Gemini + Chroma 파이프라인 실행에 필요한 설정값."""

    gemini_api_key: str
    embedding_model: str = "gemini-embedding-001"
    generation_model: str = "gemini-3.6-flash"
    embedding_output_dimensionality: int = 768
    chroma_path: Path = _REPO_ROOT / ".chroma_index"
    collection_name: str = "police_legal_corpus"
    precedent_root: Path = _REPO_ROOT / "precedent"
    statute_root: Path = _REPO_ROOT / "status" / "세부법령"
    top_k_default: int = 8
    embedding_batch_size: int = 16


class MissingApiKeyError(RuntimeError):
    """``GEMINI_API_KEY``가 환경변수 또는 ``.env``에 설정되지 않았을 때 발생한다."""


def load_settings(*, require_api_key: bool = True) -> RagSettings:
    """환경변수에서 :class:`RagSettings`를 구성한다.

    ``require_api_key=False``이면 인제스트 파싱처럼 실제 Gemini 호출이 필요 없는
    작업에서 API 키 없이도 설정을 구성할 수 있다(``gemini_api_key``는 빈 문자열).
    """
    _ensure_dotenv_loaded()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise MissingApiKeyError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. "
            "저장소 루트에 .env 파일을 만들고 GEMINI_API_KEY=발급받은키 를 추가하거나 "
            "PowerShell에서 $env:GEMINI_API_KEY=\"발급받은키\" 로 설정하세요."
        )

    def _env_path(name: str, default: Path) -> Path:
        raw = os.environ.get(name, "").strip()
        if not raw:
            return default
        candidate = Path(raw)
        # 상대 경로는 현재 작업 디렉토리가 아니라 저장소 루트를 기준으로 해석한다.
        # (uvicorn/pytest 등을 다른 작업 디렉토리에서 실행해도 경로가 흔들리지 않게 함)
        return candidate if candidate.is_absolute() else (_REPO_ROOT / candidate)

    def _env_int(name: str, default: int) -> int:
        raw = os.environ.get(name, "").strip()
        return int(raw) if raw else default

    return RagSettings(
        gemini_api_key=api_key,
        embedding_model=os.environ.get("RAG_EMBEDDING_MODEL", "gemini-embedding-001"),
        generation_model=os.environ.get("RAG_GENERATION_MODEL", "gemini-3.6-flash"),
        embedding_output_dimensionality=_env_int("RAG_EMBEDDING_DIM", 768),
        chroma_path=_env_path("RAG_CHROMA_PATH", _REPO_ROOT / ".chroma_index"),
        collection_name=os.environ.get("RAG_COLLECTION_NAME", "police_legal_corpus"),
        precedent_root=_env_path("RAG_PRECEDENT_ROOT", _REPO_ROOT / "precedent"),
        statute_root=_env_path("RAG_STATUTE_ROOT", _REPO_ROOT / "status" / "세부법령"),
        top_k_default=_env_int("RAG_TOP_K", 8),
        embedding_batch_size=_env_int("RAG_EMBEDDING_BATCH_SIZE", 16),
    )
