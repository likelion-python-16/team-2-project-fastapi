from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # SQL 쿼리 로그 출력
    pool_pre_ping=True,   # 연결 확인
    pool_recycle=300      # 5분마다 연결 갱신
)

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
    from .models import Base
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    print("✅ SQLAlchemy 2.0 방식으로 테이블 생성 완료")