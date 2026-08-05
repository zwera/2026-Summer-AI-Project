"""
FastAPI 진입점.
경찰관 공무집행 적법성 검증 및 판례 검색 AI 봇 백엔드.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, search, analysis

settings = get_settings()

app = FastAPI(
    title="경찰관 공무집행 적법성 검증 봇 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
