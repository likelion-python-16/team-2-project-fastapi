# app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 설정에서 데이터베이스 URL 가져오기
SQLALCHEMY_DATABASE_URL = settings.database_url

# 데이터베이스 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (여기서 정의하거나 models.base에서 import)


# 데이터베이스 세션 의존성
def get_db():
    """데이터베이스 세션을 제공하는 의존성 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 초기화 함수
def init_db():
    """데이터베이스 테이블 생성
    - Alembic을 사용하는 경우(이미 alembic_version 테이블이 있으면) create_all을 생략
    """
    from app.models.base import Base

    try:
        insp = inspect(engine)
        if insp.has_table('alembic_version'):
            # Alembic이 관리 중이면 스키마 관리는 마이그레이션에 위임
            return
    except Exception:
        # 검사 실패 시 보수적으로 create_all 수행
        pass

    Base.metadata.create_all(bind=engine)
    print("✅ 테이블 생성(create_all) 완료 — alembic_version 미검출")
