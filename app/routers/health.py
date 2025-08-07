from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from ..core.database import get_db
from ..core.config import settings
from ..utils.logging import logger

router = APIRouter(prefix="/health", tags=["Health Check"])

@router.get("/")
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

@router.get("/db")
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

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """상세 시스템 상태 체크"""
    try:
        # DB 연결 테스트
        db_start = datetime.now()
        result = db.execute(text("SELECT 1 as test")).fetchone()
        db_latency = (datetime.now() - db_start).total_seconds() * 1000
        
        return {
            "status": "healthy",
            "service": {
                "name": settings.project_name,
                "version": settings.project_version,
                "environment": "development" if settings.debug else "production"
            },
            "database": {
                "status": "connected" if result and result.test == 1 else "error",
                "latency_ms": round(db_latency, 2),
                "host": settings.mysql_host,
                "port": settings.mysql_port,
                "database": settings.mysql_database
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=503, detail={
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })