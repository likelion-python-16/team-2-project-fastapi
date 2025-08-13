from fastapi import APIRouter
from datetime import datetime
from ..core.config import settings

router = APIRouter(prefix="/system", tags=["System Info"])

@router.get("/info")
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
        },
        "timestamp": datetime.now().isoformat()
    }

@router.get("/version")
async def get_version():
    """버전 정보만 간단히"""
    return {
        "version": settings.project_version,
        "name": settings.project_name
    }

@router.get("/status")
async def system_status():
    """시스템 기본 상태"""
    return {
        "status": "running",
        "environment": "development" if settings.debug else "production",
        "debug_mode": settings.debug,
        "timestamp": datetime.now().isoformat()
    }