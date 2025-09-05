from ..schemas.tags import TagAIRequest, TagAIResponse, TagCreate, TagResponse, TagUpdate
from fastapi import APIRouter, Query, Depends, HTTPException
from app.services.predictor import predict_category
from ..core.database import get_db
from app.models import Tag
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tags", tags=["Tags"])

@router.get("/", response_model=list)
def get_all_tags(
    active_only: bool = Query(True, description="활성 태그만 조회"),
    limit: int = Query(50, ge=1, le=200, description="조회할 태그 수"), 
    db: Session = Depends(get_db)
):
    """태그 목록 조회 (루트 엔드포인트)"""
    from app.models import Tag
    
    query = db.query(Tag)
    if active_only:
        query = query.filter(Tag.is_active == True)
    
    tags = query.limit(limit).all()
    
    # JavaScript에서 배열을 직접 기대하므로 태그 배열만 반환
    return [{"id": tag.id, "tag": tag.tag, "is_active": tag.is_active} for tag in tags]

@router.post("/search", response_model=TagAIResponse)
def search_tags(req: TagAIRequest):
    tag, score = predict_category(req.query)
    return TagAIResponse(tag=tag, score=score)

@router.get("/search", response_model=TagAIResponse)
def search_tags_get(query: str = Query(..., description="검색어")):
    tag, score = predict_category(query)
    return TagAIResponse(tag=tag, score=score)

@router.post("/create", response_model=TagResponse)
def create_tag(tag_data: TagCreate, db: Session = Depends(get_db)):
    # 중복 태그 체크
    existing = db.query(Tag).filter(Tag.tag == tag_data.tag).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 태그입니다.")

    new_tag = Tag(
        tag=tag_data.tag,
        icon_url=tag_data.icon_url,
        is_active=True,
        embedding=None,
        embedding_model=None,
        embedding_updated_at=None
    )
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)

    return new_tag

# 태그 수정
@router.put("/update/{tag_id}", response_model=TagResponse)
def update_tag(tag_id: int, tag_data: TagUpdate, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # 중복 태그명 방지
    if tag_data.tag:
        existing = db.query(Tag).filter(Tag.tag == tag_data.tag, Tag.id != tag_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tag name already exists")

    if tag_data.tag is not None:
        tag.tag = tag_data.tag
    if tag_data.icon_url is not None:
        tag.icon_url = tag_data.icon_url

    db.commit()
    db.refresh(tag)
    return tag


# 태그 삭제
@router.delete("/delete/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(tag)
    db.commit()
    return {"message": "Tag deleted successfully"}



# 기본 카테고리 레이블(centroids) 리스트
@router.get("/defaults")
def list_default_labels():
    from app.services.store import store
    return {"labels": store.centroid_labels}

# 기본 키워드(용어)와 소속 카테고리
@router.get("/default-terms")
def list_default_terms():
    from app.services.store import store
    return {"terms": [{"term": t, "category": c} for t, c in zip(store.flat_terms, store.flat_labels)]}

@router.post("/defaults/reload")
def reload_defaults():
    from app.services.store import store
    store.load()
    return {"reloaded": True, "labels": store.centroid_labels}

@router.post("/seed-defaults")
def seed_defaults(db: Session = Depends(get_db)):
    from app.services.store import store
    from app.models import Tag
    inserted, skipped = 0, 0
    for name in store.centroid_labels:
        name = (name or "").strip()
        if not name:
            continue
        exists = db.query(Tag).filter(Tag.tag == name).first()
        if exists:
            skipped += 1
            continue
        db.add(Tag(tag=name, is_active=True))
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "total": len(store.centroid_labels)}

@router.post("/seed-categories")
def seed_categories(db: Session = Depends(get_db)):
    """category_keywords.json의 카테고리들을 태그로 추가"""
    import json
    from pathlib import Path
    from app.models import Tag
    
    # category_keywords.json 로드
    keywords_path = Path("data/category_keywords.json")
    if not keywords_path.exists():
        raise HTTPException(status_code=404, detail="category_keywords.json 파일을 찾을 수 없습니다")
    
    with open(keywords_path, 'r', encoding='utf-8') as f:
        category_keywords = json.load(f)
    
    inserted, skipped = 0, 0
    categories = list(category_keywords.keys())
    
    for category in categories:
        category = category.strip()
        if not category:
            continue
            
        exists = db.query(Tag).filter(Tag.tag == category).first()
        if exists:
            skipped += 1
            continue
            
        tag = Tag(
            tag=category,
            is_active=True,
            icon_url=None,
            embedding=None,
            embedding_model=None,
            embedding_updated_at=None
        )
        db.add(tag)
        inserted += 1
    
    db.commit()
    return {
        "inserted": inserted, 
        "skipped": skipped, 
        "total": len(categories),
        "categories": categories[:10] if len(categories) > 10 else categories  # 처음 10개만 표시
    }

@router.get("/list")
def list_tags(
    active_only: bool = Query(True, description="활성 태그만 조회"),
    limit: int = Query(50, ge=1, le=200, description="조회할 태그 수"), 
    db: Session = Depends(get_db)
):
    """데이터베이스의 모든 태그 목록 조회"""
    from app.models import Tag
    
    query = db.query(Tag)
    if active_only:
        query = query.filter(Tag.is_active == True)
    
    tags = query.limit(limit).all()
    
    return {
        "tags": [{"id": tag.id, "tag": tag.tag, "is_active": tag.is_active} for tag in tags],
        "count": len(tags),
        "total": db.query(Tag).count()
    }