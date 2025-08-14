from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.tag import Tag  # 네 프로젝트의 Tag 모델 경로에 맞춰 import

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])

@router.get("")
def search_tags(q: str = Query("", min_length=0), db: Session = Depends(get_db)):
    """태그 자동완성: 부분 일치 20개"""
    q = q.strip()
    query = db.query(Tag)
    if q:
        query = query.filter(Tag.name.like(f"%{q}%"))
    names = [t.name for t in query.order_by(Tag.name.asc()).limit(20).all()]
    return {"items": names}
