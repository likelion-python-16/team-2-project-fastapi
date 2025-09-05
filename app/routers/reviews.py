from typing import List, Dict, Any
from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.security import get_current_user_optional
from app.models.user import User
from app.models.participation import Participation
from app.models.challenge import Challenge
from app.models.review import Review, ReviewStatus

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/api", tags=["reviews-pages"])  # HTML 페이지 라우트


def _user_display(u: User) -> Dict[str, Any]:
    name = (u.name or u.username or f"User {u.id}")
    avatar = getattr(u, "profile_image", None) or "/static/pictures/defaultprofile.jpeg"
    return {"id": u.id, "name": name, "avatar_url": avatar}


@router.get("/reviews", name="review_list_page", response_class=HTMLResponse)
def review_list_page(
    request: Request,
    challenge_id: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    me: User | None = Depends(get_current_user_optional),
):
    # 참가자 목록(간단 조회)
    rows = (
        db.query(User)
        .join(Participation, Participation.user_id == User.id)
        .filter(Participation.challenge_id == challenge_id)
        .all()
    )
    # 자신 제외
    if me is not None:
        rows = [u for u in rows if getattr(u, "id", None) != getattr(me, "id", None)]
    members = [_user_display(u) for u in rows]
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    challenge_title = (ch.title if ch else f"Challenge #{challenge_id}")
    # 서버단에선 reviewed 알 수 없으므로 false. 클라이언트가 /api/v1/challenges/{id}/reviews/mine로 보강
    for m in members:
        m["reviewed"] = False

    return templates.TemplateResponse(
        "review_list.html",
        {"request": request, "members": members, "challenge_id": challenge_id, "challenge_title": challenge_title},
    )


@router.get("/reviews/write", name="review_write_page", response_class=HTMLResponse)
def review_write_page(request: Request, user_id: int = Query(..., ge=1), challenge_id: int = Query(1, ge=1), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    challenge_title = (ch.title if ch else f"Challenge #{challenge_id}")
    target = _user_display(u) if u else {"id": user_id, "name": f"User {user_id}", "avatar_url": None}
    return templates.TemplateResponse(
        "review_write.html",
        {"request": request, "target": target, "challenge_id": challenge_id, "user_id": user_id, "challenge_title": challenge_title},
    )


@router.get("/my-reviews", name="my_review_page", response_class=HTMLResponse)
def my_review_page(
    request: Request,
    challenge_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    me: User | None = Depends(get_current_user_optional),
):
    # 서버에서도 가능하면 미리 채워서 렌더 (토큰 있을 때)
    rows = []
    if me is not None:
        q = db.query(Review).filter(Review.user_id == me.id, Review.status != ReviewStatus.deleted)
        if challenge_id:
            q = q.filter(Review.challenge_id == challenge_id)
        reviews = q.order_by(Review.id.desc()).limit(20).all()
        for r in reviews:
            tu = getattr(r, 'target_user', None)
            rows.append({
                'id': r.id,
                'comment': r.comment,
                'rating': float(r.rating or 0),
                'updated_at': r.updated_at,
                'member': {
                    'id': getattr(tu, 'id', None),
                    'name': getattr(tu, 'name', None) or getattr(tu, 'username', None) or 'Unknown',
                    'avatar_url': getattr(tu, 'profile_image', None),
                },
            })
    return templates.TemplateResponse(
        "my_review.html",
        {"request": request, "rows": rows, "challenge_id": challenge_id},
    )


@router.get("/reviews/challenge", name="reviews_challenge", response_class=HTMLResponse)
def reviews_challenge(request: Request, challenge_id: int | None = None):
    return templates.TemplateResponse(
        "review_challenge.html",
        {"request": request, "challenge_id": challenge_id},
    )


@router.get("/reviews/received", name="received_reviews_page", response_class=HTMLResponse)
def received_reviews_page(request: Request):
    """받은 리뷰 목록 페이지"""
    return templates.TemplateResponse(
        "received_reviews.html",
        {"request": request},
    )
