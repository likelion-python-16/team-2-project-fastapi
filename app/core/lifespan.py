from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db
from .config import settings
from ..utils.logging import logger
from app.services.map_version import start_version_refresher

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 Startup
    logger.info("🚀 FastAPI 서버가 시작됩니다...")
    
    # DB 초기화
    try:
        init_db()
        logger.info("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
    
    # 백그라운드 태스크 시작
    import asyncio
    task = asyncio.create_task(start_version_refresher())
    
    try:
        yield
    finally:
        # 🛑 Shutdown
        logger.info("🛑 FastAPI 서버가 종료됩니다...")
        task.cancel()