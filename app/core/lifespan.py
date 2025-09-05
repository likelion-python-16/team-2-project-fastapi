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
            # 이미 존재하는 태그 집합
            existing_tags = {row[0] for row in db.query(Tag.tag).all()}

            # 카테고리 라벨(예: 17개)만 대상으로 누락된 것만 추가
            labels = [(name or "").strip() for name in store.centroid_labels]
            labels = [name for name in labels if name]
            missing = [name for name in labels if name not in existing_tags]

            if missing:
                for name in missing:
                    db.add(Tag(tag=name, is_active=True))
                db.commit()
                logger.info(f"카테고리 라벨 시드 완료. 추가된 라벨 수: {len(missing)}개")
            else:
                logger.info("추가할 카테고리 라벨이 없습니다")
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
    
    # DM 컨테이너 챌린지 로직 제거 (challenge_id NULL 허용으로 대체)
    
    try:
        yield
    finally:
        # 🛑 Shutdown
        logger.info("🛑 FastAPI 서버가 종료됩니다...")
        task.cancel()
