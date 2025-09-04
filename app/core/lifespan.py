from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db
# from .config import settings  # unused
from ..utils.logging import logger
from app.services.map_version import start_version_refresher

@asynccontextmanager
async def lifespan(_: FastAPI):
    # 🚀 Startup
    logger.info("🚀 FastAPI 서버가 시작됩니다...")
    
    # DB 초기화
    try:
        init_db()
        logger.info("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
    
    # 초기 관리자 생성
    try:
        from app.scripts.create_initial_admin import create_initial_admin
        if create_initial_admin():
            logger.info("✅ 초기 관리자 설정 완료")
        else:
            logger.warning("⚠️  초기 관리자 설정을 건너뜀")
    except Exception as e:
        logger.warning(f"⚠️  초기 관리자 생성 중 오류: {e}")
    
    # 태그 시드 실행
    try:
        from app.core.database import SessionLocal
        from app.models import Tag
        from app.services.store import store
        
        db = SessionLocal()
        try:
            existing_count = db.query(Tag).count()
            if existing_count < 100:
                logger.info(f"현재 태그 수: {existing_count}개, 태그 시드 실행 중...")
                
                for name in store.centroid_labels:
                    name = (name or "").strip()
                    if not name:
                        continue
                    exists = db.query(Tag).filter(Tag.tag == name).first()
                    if not exists:
                        db.add(Tag(tag=name, is_active=True))
                
                for _, keywords in store.categories.items():
                    for keyword in keywords[:20]:
                        keyword = (keyword or "").strip()
                        if not keyword:
                            continue
                        exists = db.query(Tag).filter(Tag.tag == keyword).first()
                        if not exists:
                            db.add(Tag(tag=keyword, is_active=True))
                
                db.commit()
                new_count = db.query(Tag).count()
                logger.info(f"태그 시드 완료. 총 태그 수: {new_count}개")
            else:
                logger.info(f"태그가 이미 충분히 존재합니다: {existing_count}개")
        except Exception as e:
            logger.error(f"태그 시드 실행 중 오류: {e}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"⚠️ 태그 시드 중 오류: {e}")
    
    # 백그라운드 태스크 시작
    import asyncio
    task = asyncio.create_task(start_version_refresher())
    
    try:
        yield
    finally:
        # 🛑 Shutdown
        logger.info("🛑 FastAPI 서버가 종료됩니다...")
        task.cancel()