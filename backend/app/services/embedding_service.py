"""
로컬 GPU 기반 임베딩 서비스 (BAAI/bge-m3).

RTX 3070 8GB 환경에서 fp16으로 로드해 VRAM 사용량을 낮춘다.
모델은 프로세스당 한 번만 로드되도록 싱글턴으로 관리한다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np

from app.config import get_settings


@lru_cache
def _get_model():
    from FlagEmbedding import BGEM3FlagModel

    settings = get_settings()
    use_fp16 = settings.embedding_device.startswith("cuda")
    model = BGEM3FlagModel(
        settings.embedding_model,
        use_fp16=use_fp16,
        devices=settings.embedding_device,
    )
    return model


def embed_texts(texts: Sequence[str], batch_size: int = 12, max_length: int = 1024) -> np.ndarray:
    """문서/질의 텍스트 목록을 dense 벡터 배열로 변환."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_model()
    output = model.encode(
        list(texts),
        batch_size=batch_size,
        max_length=max_length,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return np.asarray(output["dense_vecs"], dtype=np.float32)


def embed_query(query: str, max_length: int = 512) -> np.ndarray:
    """검색 질의 하나를 임베딩. (bge-m3는 query/passage 구분 없이 사용 가능)"""
    vecs = embed_texts([query], batch_size=1, max_length=max_length)
    return vecs[0]
