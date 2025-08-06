from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.database_url,  # DATABASE_URL → database_url
    echo=settings.debug,    # DEBUG → debug
    pool_pre_ping=True,     # 연결 확인
    pool_recycle=300        # 5분마다 연결 갱신
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 베이스 클래스
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
    Base.metadata.create_all(bind=engine)