# app/core/database.py  (최종본)
from app.db.session import engine, SessionLocal, get_db  # 재노출만
# Base는 모듈 상단에서 import 하지 않음!

def init_db() -> None:
    from app.models.base import Base   # 지연 import로 순환 방지
    Base.metadata.create_all(bind=engine)
