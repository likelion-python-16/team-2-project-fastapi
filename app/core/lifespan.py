from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db
from .config import settings
from ..utils.logging import logger
from app.services.map_version import start_version_refresher

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리 (startup/shutdown 이벤트 대체)"""
    # 🚀 Startup
    logger.info("🚀 FastAPI 서버가 시작됩니다...")
    logger.info(f"📊 데이터베이스: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")
    logger.info(f"🌍 환경: {'개발' if settings.debug else '운영'}")
    
    try:
        init_db()
        logger.info("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
        # 초기화 실패해도 서버는 시작되도록 함
    
    yield
    
    # 🛑 Shutdown
    logger.info("🛑 FastAPI 서버가 종료됩니다...")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 백그라운드 태스크 시작
        import asyncio
        task = asyncio.create_task(start_version_refresher())
        try:
            yield
        finally:
            task.cancel()