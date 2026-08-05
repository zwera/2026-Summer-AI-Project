"""Chroma 임베디드 벡터 인덱스 관리.

``chromadb.PersistentClient``로 로컬 디스크(``RagSettings.chroma_path``)에 컬렉션을
저장한다. 별도 서버 프로세스가 필요 없고, 프로세스 재시작 후에도 같은 경로에서 그대로
재사용할 수 있다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Sequence, Union

import chromadb
from chromadb.api.models.Collection import Collection

from rag.config import RagSettings
from rag.embedding import GeminiEmbedder
from rag.ingest import build_all_chunks
from rag.schemas import Chunk

_LOGGER = logging.getLogger(__name__)


def get_chroma_client(settings: RagSettings) -> chromadb.ClientAPI:
    """설정된 경로의 임베디드(로컬 파일 기반) Chroma 클라이언트를 반환한다."""
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_path))


def get_collection(client: chromadb.ClientAPI, settings: RagSettings) -> Collection:
    """설정된 이름의 컬렉션을 가져오거나 새로 만든다."""
    return client.get_or_create_collection(
        name=settings.collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def build_index(
    settings: RagSettings,
    embedder: GeminiEmbedder,
    *,
    force_rebuild: bool = False,
) -> int:
    """판례·법령 원문을 청크로 분할해 Gemini로 임베딩하고 Chroma에 저장한다.

    이미 컬렉션에 데이터가 있고 ``force_rebuild=False``이면 재임베딩을 건너뛰고
    현재 저장된 청크 수를 그대로 반환한다(재시작 시 재사용, API 비용 절감).

    Returns:
        인덱싱 이후 컬렉션에 저장된 총 청크 수.
    """
    client = get_chroma_client(settings)
    collection = get_collection(client, settings)

    existing_count = int(collection.count())
    if existing_count > 0 and not force_rebuild:
        _LOGGER.info(
            "chroma_index_reused", extra={"collection": settings.collection_name, "count": existing_count}
        )
        return existing_count

    if force_rebuild and existing_count > 0:
        client.delete_collection(settings.collection_name)
        collection = get_collection(client, settings)

    chunks = build_all_chunks(settings.precedent_root, settings.statute_root)
    if not chunks:
        _LOGGER.warning("chroma_index_no_chunks_found")
        return 0

    _add_chunks_in_batches(collection, chunks, embedder)
    return int(collection.count())


def _add_chunks_in_batches(
    collection: Collection, chunks: Sequence[Chunk], embedder: GeminiEmbedder
) -> None:
    batch_size = embedder._settings.embedding_batch_size  # noqa: SLF001 - 동일 모듈 내부 설정 재사용
    for start in range(0, len(chunks), batch_size):
        batch = list(chunks[start : start + batch_size])
        texts = [chunk.text for chunk in batch]
        vectors = embedder.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            embeddings=vectors,
            documents=texts,
            metadatas=[_sanitize_metadata(chunk) for chunk in batch],
        )
        _LOGGER.info(
            "chroma_index_batch_added",
            extra={"start": start, "batch_size": len(batch), "total": len(chunks)},
        )


def _sanitize_metadata(chunk: Chunk) -> Dict[str, Union[str, int, float, bool]]:
    """Chroma 메타데이터는 str/int/float/bool만 허용하므로 값을 정규화한다."""
    metadata: Dict[str, Union[str, int, float, bool]] = {"doc_type": chunk.doc_type}
    for key, value in chunk.metadata.items():
        if value is None:
            metadata[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = str(value)
    return metadata


def reset_index(settings: RagSettings) -> None:
    """컬렉션을 완전히 삭제한다(재인덱싱 강제용, 테스트 정리용)."""
    client = get_chroma_client(settings)
    try:
        client.delete_collection(settings.collection_name)
    except Exception:  # noqa: BLE001 - 컬렉션이 존재하지 않는 경우도 정상 종료로 취급
        pass
