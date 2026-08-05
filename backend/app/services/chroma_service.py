"""
ChromaDB 클라이언트/컬렉션 관리.

별도 서버 없이 로컬 디스크에 영속화되는 PersistentClient를 사용한다.
임베딩은 우리가 직접 bge-m3로 계산해서 넣으므로 컬렉션에는
embedding_function을 지정하지 않는다 (add/query 시 embeddings를 직접 전달).
"""
from __future__ import annotations

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import get_settings

STATUTE_COLLECTION_NAME = "statutes"
PRECEDENT_COLLECTION_NAME = "precedents"


def _check_ascii_path(path) -> None:
    """비ASCII(한글 등) 경로를 미리 감지해 조기에 에러를 낸다.

    ChromaDB가 내부적으로 쓰는 hnswlib(C++ 확장모듈)은 Windows에서
    비ASCII 경로의 벡터 인덱스 파일(header.bin 등)을 열 때 에러 없이
    조용히 실패하는 경우가 있다(파일이 생성되지 않음). 그 결과 저장은
    되는 것처럼 보이지만(count는 정상), 프로세스를 재시작해 인덱스를
    다시 열면 "Cannot open header file" RuntimeError가 발생한다.
    이 문제를 원인 파악이 어려운 런타임 에러 대신 명확한 메시지로
    조기에 알려준다.
    """
    try:
        str(path).encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            "CHROMA_PERSIST_DIR 경로에 한글 등 비ASCII 문자가 포함되어 있습니다: "
            f"{path}\n"
            "ChromaDB가 사용하는 hnswlib이 Windows에서 이런 경로의 벡터 인덱스"
            " 파일을 제대로 열지 못하는 문제가 있습니다(조용히 실패하다가 나중에"
            " 'Cannot open header file' 에러로 나타남).\n"
            "backend/.env 의 CHROMA_PERSIST_DIR을 영문 경로로 바꿔주세요."
            " 예) C:/Users/사용자명/.police_bot_chroma_data"
        ) from exc


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    _check_ascii_path(settings.chroma_persist_path)
    settings.chroma_persist_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_persist_path))


def get_statute_collection(create: bool = True) -> Collection:
    client = get_chroma_client()
    if create:
        return client.get_or_create_collection(
            STATUTE_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(STATUTE_COLLECTION_NAME)


def get_precedent_collection(create: bool = True) -> Collection:
    client = get_chroma_client()
    if create:
        return client.get_or_create_collection(
            PRECEDENT_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(PRECEDENT_COLLECTION_NAME)


def reset_collections() -> None:
    """기존 컬렉션을 삭제하고 다시 생성 (재인덱싱 시 사용)."""
    client = get_chroma_client()
    for name in (STATUTE_COLLECTION_NAME, PRECEDENT_COLLECTION_NAME):
        try:
            client.delete_collection(name)
        except Exception:
            pass
    get_statute_collection()
    get_precedent_collection()
