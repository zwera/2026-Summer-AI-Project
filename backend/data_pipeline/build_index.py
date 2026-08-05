"""
Part 2: 임베딩 서비스 구현 및 ChromaDB 인덱싱 파이프라인.

data_processed/statutes.json, data_processed/precedents.json 을 읽어
BAAI/bge-m3(GPU)로 임베딩한 뒤 ChromaDB(로컬 파일 기반)에 저장한다.

사용법:
    python -m data_pipeline.build_index            # 증분 인덱싱 (기존 컬렉션 유지)
    python -m data_pipeline.build_index --reset     # 컬렉션을 초기화하고 새로 인덱싱
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from app.services.chroma_service import (
    get_precedent_collection,
    get_statute_collection,
    reset_collections,
)
from app.services.embedding_service import embed_texts
from app.taxonomy import LAW_AREA_DEFAULT_CATEGORY
from data_pipeline.chunking import chunk_text

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data_processed"
STATUTES_PATH = DATA_DIR / "statutes.json"
PRECEDENTS_PATH = DATA_DIR / "precedents.json"

EMBED_BATCH_SIZE = 16
CHROMA_UPSERT_BATCH_SIZE = 64


def _batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def index_statutes() -> int:
    if not STATUTES_PATH.exists():
        print(f"[경고] {STATUTES_PATH} 가 없습니다. parse_statutes를 먼저 실행하세요.")
        return 0

    statutes = json.loads(STATUTES_PATH.read_text(encoding="utf-8"))
    collection = get_statute_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for article in statutes:
        content = (article.get("content") or "").strip()
        if not content:
            continue
        ids.append(article["id"])
        documents.append(f"{article['law_name']} {article['article_no']}({article['article_title']}) {content}")
        metadatas.append(
            {
                "law_name": article["law_name"],
                "law_kind": article.get("law_kind", ""),
                "article_no": article["article_no"],
                "article_title": article["article_title"],
                "content": content[:2000],
                "source_file": article.get("source_file", ""),
            }
        )

    print(f"법령 조문 {len(ids)}건 임베딩 및 인덱싱 시작...")
    total = 0
    for id_batch, doc_batch, meta_batch in zip(
        _batched(ids, CHROMA_UPSERT_BATCH_SIZE),
        _batched(documents, CHROMA_UPSERT_BATCH_SIZE),
        _batched(metadatas, CHROMA_UPSERT_BATCH_SIZE),
    ):
        embeddings = embed_texts(doc_batch, batch_size=EMBED_BATCH_SIZE, max_length=512)
        collection.upsert(
            ids=id_batch,
            embeddings=embeddings.tolist(),
            documents=doc_batch,
            metadatas=meta_batch,
        )
        total += len(id_batch)
        print(f"  ... {total}/{len(ids)}")

    print(f"법령 조문 인덱싱 완료: {total}건")
    return total


def index_precedents() -> int:
    if not PRECEDENTS_PATH.exists():
        print(f"[경고] {PRECEDENTS_PATH} 가 없습니다. parse_precedents를 먼저 실행하세요.")
        return 0

    precedents = json.loads(PRECEDENTS_PATH.read_text(encoding="utf-8"))
    collection = get_precedent_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for prec in tqdm(precedents, desc="문서 구성"):
        law_area = prec.get("law_area", "") or prec.get("category", "")
        job_category = LAW_AREA_DEFAULT_CATEGORY.get(law_area, "uncategorized")
        base_meta = {
            "precedent_id": prec["id"],
            "case_no": prec.get("case_no", ""),
            "title": prec.get("title", ""),
            "date": prec.get("date", ""),
            "court": prec.get("court", ""),
            "case_type": prec.get("case_type", ""),
            "judgment_type": prec.get("judgment_type", ""),
            "instance": prec.get("instance", ""),
            "category": prec.get("category", ""),
            "law_area": law_area,
            # 경찰 직무 시나리오 카테고리 (app/taxonomy.py JOB_CATEGORIES 의 key).
            # 검색 시 category 파라미터로 필터링하는 데 사용한다.
            "job_category": job_category,
            "source_link": prec.get("source_link", ""),
            "source_file": prec.get("source_file", ""),
        }

        # 1) digest 문서: 제목 + 판시사항 + 판결요지 (짧고 핵심적, 유사도 매칭에 주력)
        digest_parts = [prec.get("title", ""), prec.get("summary", ""), prec.get("gist", "")]
        digest_text = "\n".join(p for p in digest_parts if p).strip()
        if digest_text:
            ids.append(f"{prec['id']}::digest")
            documents.append(digest_text)
            metadatas.append({**base_meta, "part": "digest", "chunk_index": 0})

        # 2) 전문 청크: 상세 사실관계/판단 근거 검색용
        full_text = prec.get("full_text", "") or ""
        chunks = chunk_text(full_text, chunk_size=1200, overlap=150)
        for i, chunk in enumerate(chunks):
            ids.append(f"{prec['id']}::chunk{i}")
            documents.append(chunk)
            metadatas.append({**base_meta, "part": "full_text", "chunk_index": i})

        # digest도 full_text도 없으면 스킵 (거의 없을 것으로 예상)

    print(f"판례 문서(청크 포함) {len(ids)}건 임베딩 및 인덱싱 시작...")
    total = 0
    for id_batch, doc_batch, meta_batch in zip(
        _batched(ids, CHROMA_UPSERT_BATCH_SIZE),
        _batched(documents, CHROMA_UPSERT_BATCH_SIZE),
        _batched(metadatas, CHROMA_UPSERT_BATCH_SIZE),
    ):
        embeddings = embed_texts(doc_batch, batch_size=EMBED_BATCH_SIZE, max_length=1024)
        collection.upsert(
            ids=id_batch,
            embeddings=embeddings.tolist(),
            documents=doc_batch,
            metadatas=meta_batch,
        )
        total += len(id_batch)
        print(f"  ... {total}/{len(ids)}")

    print(f"판례 인덱싱 완료: {total}건 (원본 판례 {len(precedents)}건)")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="ChromaDB 인덱싱 파이프라인")
    parser.add_argument("--reset", action="store_true", help="기존 컬렉션을 삭제하고 새로 인덱싱")
    args = parser.parse_args()

    if args.reset:
        print("기존 컬렉션 초기화 중...")
        reset_collections()

    statute_count = index_statutes()
    precedent_count = index_precedents()

    print(f"\n=== 인덱싱 요약 ===\n법령 조문: {statute_count}건\n판례 문서: {precedent_count}건")


if __name__ == "__main__":
    main()
