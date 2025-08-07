from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# 설정 및 라이프사이클
from .core.config import settings
from .core.lifespan import lifespan

# 로깅 설정
from .utils.logging import logger

# 라우터들
from .routers import users, health, system

# FastAPI 앱 생성
app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🏠 루트 엔드포인트 (메인에 하나만 남김)
@app.get("/", tags=["Root"])
async def read_root():
    """루트 엔드포인트 - API 소개"""
    return {
        "message": f"환영합니다! {settings.project_name} API",
        "version": settings.project_version,
        "docs": "/docs",
        "health": "/health",
        "info": "/system/info",
        "timestamp": datetime.now().isoformat()
    }

# 📍 라우터 등록
app.include_router(health.router)           # /health/*
app.include_router(system.router)          # /system/*
app.include_router(users.router, prefix="/api/v1")  # /api/v1/users/*

# TODO: 추가 라우터들
# app.include_router(auth.router, prefix="/api/v1")      # /api/v1/auth/*
# app.include_router(challenges.router, prefix="/api/v1") # /api/v1/challenges/*
# app.include_router(qr.router, prefix="/api/v1")        # /api/v1/qr/*

# 🚀 서버 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버를 직접 실행합니다...")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )