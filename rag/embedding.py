"""Gemini 임베딩 API 호출을 감싸는 얇은 래퍼.

``google-genai`` SDK의 ``client.models.embed_content``만 사용하며, 배치 크기 제한과
task_type(색인용 RETRIEVAL_DOCUMENT / 질의용 RETRIEVAL_QUERY) 구분을 담당한다.
"""
from __future__ import annotations

from typing import List, Literal, Sequence

from google import genai
from google.genai import types

from rag.config import RagSettings

EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class GeminiEmbedder:
    """``RagSettings``에 지정된 임베딩 모델로 텍스트를 벡터로 변환한다."""

    def __init__(self, settings: RagSettings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def embed_texts(
        self, texts: Sequence[str], *, task_type: EmbeddingTaskType
    ) -> List[List[float]]:
        """텍스트 목록을 임베딩 벡터 목록으로 변환한다(배치 크기 제한 적용)."""
        if not texts:
            return []
        vectors: List[List[float]] = []
        batch_size = self._settings.embedding_batch_size
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            result = self._client.models.embed_content(
                model=self._settings.embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._settings.embedding_output_dimensionality,
                ),
            )
            vectors.extend(embedding.values for embedding in result.embeddings)
        return vectors

    def embed_query(self, text: str) -> List[float]:
        """단일 질의 문자열을 검색용(``RETRIEVAL_QUERY``) 벡터로 변환한다."""
        return self.embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
