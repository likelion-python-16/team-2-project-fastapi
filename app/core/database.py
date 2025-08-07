from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings


SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
# 데이터베이스 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)
# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    from ..models.base import Base
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    print("✅ SQLAlchemy 2.0 방식으로 테이블 생성 완료")