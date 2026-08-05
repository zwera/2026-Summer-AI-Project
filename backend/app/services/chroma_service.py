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


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
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
