from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db
# from .config import settings  # unused
from ..utils.logging import logger
from app.services.map_version import start_version_refresher
from pathlib import Path
import shutil

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

    # 기본 커버 이미지 보장: challengersdefaultimage.png 가 없으면 기본 프로필 이미지로 복사
    try:
        static_dir = Path("app") / "static"
        covers_dir = static_dir / "uploads" / "challenges" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        default_src = static_dir / "pictures" / "defaultprofile.jpeg"
        default_dst = covers_dir / "challengersdefaultimage.png"
        fallback_dst = covers_dir / "challengersdefaultimage1.png"
        if default_src.exists():
            if not default_dst.exists():
                shutil.copyfile(default_src, default_dst)
                logger.info("✅ 기본 커버 이미지(challengersdefaultimage.png) 생성")
            if not fallback_dst.exists():
                shutil.copyfile(default_src, fallback_dst)
        else:
            logger.warning("⚠️ 기본 프로필 이미지가 없어 커버 기본 생성은 건너뜁니다")
    except Exception as e:
        logger.warning(f"⚠️ 기본 커버 이미지 보장 중 오류: {e}")
    
    # 백그라운드 태스크 시작
    import asyncio
    task = asyncio.create_task(start_version_refresher())
    
    try:
        yield
    finally:
        # 🛑 Shutdown
        logger.info("🛑 FastAPI 서버가 종료됩니다...")
        task.cancel()
