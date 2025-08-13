# app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings

# 설정에서 데이터베이스 URL 가져오기
SQLALCHEMY_DATABASE_URL = settings.database_url

# 데이터베이스 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (여기서 정의하거나 models.base에서 import)
Base = declarative_base()

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
    """데이터베이스 테이블 생성"""
    # models.py에서 Base를 import
    from app.models.base import Base
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    print("✅ SQLAlchemy 2.0 방식으로 테이블 생성 완료")