from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging
from contextlib import asynccontextmanager
from .config import settings
from .database import get_db, init_db

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리 (startup/shutdown 이벤트 대체)"""
    # Startup
    logger.info("🚀 FastAPI 서버가 시작됩니다...")
    logger.info(f"📊 데이터베이스: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")
    
    try:
        init_db()
        logger.info("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
        # 초기화 실패해도 서버는 시작되도록 함
    
    yield
    
    # Shutdown
    logger.info("🛑 FastAPI 서버가 종료됩니다...")

# FastAPI 앱 생성 (lifespan 추가)
app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용: 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기본 엔드포인트들
@app.get("/")
async def read_root():
    """루트 엔드포인트"""
    return {
        "message": f"환영합니다! {settings.project_name}",
        "version": settings.project_version,
        "docs": "/docs",
        "health": "/health",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """기본 헬스 체크 엔드포인트 (DB 의존성 없음)"""
    try:
        return {
            "status": "healthy",
            "service": "running",
            "version": settings.project_version,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail={
            "status": "unhealthy",
            "service": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

@app.get("/health/db")
async def health_check_with_db(db: Session = Depends(get_db)):
    """데이터베이스 포함 상세 헬스 체크 엔드포인트"""
    try:
        # 데이터베이스 연결 테스트
        result = db.execute(text("SELECT 1 as test")).fetchone()
        db_status = "connected" if result and result.test == 1 else "error"
        
        return {
            "status": "healthy",
            "service": "running",
            "database": db_status,
            "version": settings.project_version,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy", 
            "service": "running",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/info")
async def app_info():
    """애플리케이션 정보 엔드포인트"""
    return {
        "name": settings.project_name,
        "description": settings.project_description,
        "version": settings.project_version,
        "debug": settings.debug,
        "environment": "development" if settings.debug else "production",
        "database": {
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "database": settings.mysql_database
        }
    }

# TODO: 여기에 팀에서 개발할 라우터들을 추가하세요
# 예시:
# from .routers import users, posts, comments
# app.include_router(users.router, prefix="/api/v1")
# app.include_router(posts.router, prefix="/api/v1")
# app.include_router(comments.router, prefix="/api/v1")

from .routers import users
app.include_router(users.router,prefix="/api/v1")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )