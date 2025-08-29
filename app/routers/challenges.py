# app/routers/challenges.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from typing import List, Optional, Literal
from datetime import date, time

from app.core.database import get_db

# Models
from app.models.user import User
from app.models.challenge import Challenge
from app.models.participation import Participation, ParticipationRole
from app.models.challenge_round import ChallengeRound
from app.models.round_manager import RoundManager
from app.models.attendance import RoundAttendance
from app.models.tag import Tag, ChallengeTag
from app.models.round_picture import RoundPicture

# Schemas
from app.schemas.challenge import (
    ChallengeCreate, ChallengeResponse, ChallengeUpdate, ChallengeStatus,
    DualSearchResponse, ChallengeItem
)
from app.schemas.challenge_round import (
    ChallengeRoundCreate, ChallengeRoundUpdate, ChallengeRoundResponse,
)

# Services & AuthZ
from app.services.predictor import predict_category
from app.services.challenge_round_service import auto_create_rounds_on_challenge_create
from app.core.authz import can_edit_round, is_challenge_owner, is_challenge_manager

router = APIRouter(prefix="/challenges", tags=["challenges"])

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def get_current_user_id() -> int:
    # TODO: replace with real auth
    return 1

def _fee_validation(
    fee: Optional[int],
    participation_fee: Optional[int],
    require_at_least_one: bool = False,
) -> None:
    f = 0 if fee is None else fee
    p = 0 if participation_fee is None else participation_fee
    if f < 0 or p < 0:
        raise HTTPException(400, "Fee and participation_fee must be ≥ 0.")
    if require_at_least_one and (f == 0 and p == 0):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "At least one of fee or participation_fee must be > 0.")

def _validate_common_business_rules(
    start_date: Optional[date],
    end_date: Optional[date],
    fee: Optional[int],
    participation_fee: Optional[int],
) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date must be ≤ end_date")
    if fee is not None and fee < 0:
        raise HTTPException(400, "Fee cannot be negative")
    if participation_fee is not None and participation_fee < 0:
        raise HTTPException(400, "Participation fee cannot be negative")
    if participation_fee is not None and participation_fee > 10000:
        raise HTTPException(400, "Participation fee cannot exceed 10,000 KRW")
    _fee_validation(fee, participation_fee, require_at_least_one=False)

def _round_has_dependents(r: ChallengeRound) -> bool:
    return bool(
        (getattr(r, "attendances", None) and len(r.attendances) > 0)
        or (getattr(r, "proofs", None) and len(r.proofs) > 0)
        or (getattr(r, "qrcodes", None) and len(r.qrcodes) > 0)
        or (getattr(r, "reviews", None) and len(r.reviews) > 0)
    )

def _reconcile_total_rounds(db: Session, challenge: Challenge, new_total: Optional[int], force: bool = False) -> None:
    # ✅ 서버 측 안전장치 (스키마에서 1..50 검증하더라도 추가로 방어)
    if new_total is not None and new_total > 50:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "total_rounds cannot exceed 50")

    if new_total is None:
        return
    existing = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge.id)
        .order_by(ChallengeRound.round.asc())
        .all()
    )
    cur_n = len(existing)
    if new_total == cur_n:
        return

    # 확장
    if new_total > cur_n:
        if cur_n > 0:
            base_mode = existing[-1].mode
        else:
            ch_mode = (challenge.mode or "online")
            if ch_mode == "hybrid":
                has_offline_default = bool(
                    getattr(challenge, "default_place_name", None) or
                    getattr(challenge, "default_road_address", None) or
                    (getattr(challenge, "default_latitude", None) is not None and
                     getattr(challenge, "default_longitude", None) is not None)
                )
                base_mode = "offline" if has_offline_default else "online"
            else:
                base_mode = ch_mode
        for i in range(cur_n + 1, new_total + 1):
            db.add(ChallengeRound(
                challenge_id=challenge.id,
                round=i,
                mode=base_mode,
                processing_at=challenge.start_date or date.today(),
                start_time=time(9, 0),
                finish_time=time(10, 0),
                description=f"Round {i}",
                url=(challenge.default_zoom_link if base_mode == "online" else None),
                place_name=(challenge.default_place_name if base_mode == "offline" else None),
                road_address=(challenge.default_road_address if base_mode == "offline" else None),
                lat=challenge.default_latitude,
                lon=challenge.default_longitude,
                geofence_radius_m=100.0,
            ))
        db.flush()
        return

    # 축소
    to_delete = [r for r in existing if r.round > new_total]
    for r in reversed(to_delete):
        if _round_has_dependents(r) and not force:
            raise HTTPException(409, f"Round {r.round} has dependent data; pass force=true to remove.")
        db.delete(r)
    db.flush()

def _calculate_status(ch: Challenge, db: Session, today: date) -> str:
    participants_count = db.query(Participation).filter(Participation.challenge_id == ch.id).count()
    if ch.is_closed:
        return "completed"
    if ch.end_date and today > ch.end_date:
        return "completed"
    if ch.start_date and today < ch.start_date:
        return "recruiting"
    if ch.start_date and today >= ch.start_date:
        if participants_count < (ch.min_participants or 1):
            return "recruiting"
        if not ch.end_date or today <= ch.end_date:
            return "active"
    return "recruiting"

def _can_edit_challenge(db: Session, challenge_id: int, me: int) -> bool:
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        return False
    return ch.creator_id == me or is_challenge_manager(db, challenge_id, me)

# ---- tags helpers ----
def _challenge_tags(db: Session, challenge_id: int) -> List[str]:
    rows = (
        db.query(Tag)
        .join(ChallengeTag, ChallengeTag.tag_id == Tag.id)
        .filter(ChallengeTag.challenge_id == challenge_id)
        .order_by(Tag.tag.asc())
        .all()
    )
    return [t.tag for t in rows]

def _with_tags(db: Session, ch: Challenge) -> dict:
    resp = ChallengeResponse.model_validate(ch).model_dump()
    resp["tags"] = _challenge_tags(db, ch.id)
    return resp

# Pydantic v2: 응답 모델 확장 (tags 추가)
class ChallengeResponseWithTags(ChallengeResponse):  # type: ignore[misc]
    tags: List[str] = []

# -------------------------------------------------------------------
# Search (with AI tag recommendation)
# -------------------------------------------------------------------
@router.get(
    "/search",
    response_model=DualSearchResponse,
    summary="검색어(선택)+날짜 필터+상태(기본 recruiting)+정렬 + AI 태그 추천"
)
def dual_search(
    q: Optional[str] = Query(None, description="검색어 (선택)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Literal["recruiting", "active", "completed", "cancelled"] = Query(
        "recruiting", alias="status"
    ),
    start_from: Optional[date] = Query(None), start_to: Optional[date] = Query(None),
    end_from: Optional[date] = Query(None),   end_to: Optional[date] = Query(None),
    sort_by: Literal["created_at", "start_date", "end_date", "title"] = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
):
    def apply_filters(query):
        query = query.filter(Challenge.status == status_filter)
        if start_from is not None:
            query = query.filter(Challenge.start_date >= start_from)
        if start_to is not None:
            query = query.filter(Challenge.start_date <= start_to)
        if end_from is not None:
            query = query.filter(Challenge.end_date >= end_from)
        if end_to is not None:
            query = query.filter(Challenge.end_date <= end_to)
        return query

    def apply_sorting(query):
        col_map = {
            "created_at": getattr(Challenge, "created_at", Challenge.id),
            "start_date": Challenge.start_date,
            "end_date": Challenge.end_date,
            "title": Challenge.title,
        }
        col = col_map.get(sort_by, getattr(Challenge, "created_at", Challenge.id))
        return query.order_by(asc(col) if sort_dir == "asc" else desc(col))

    base = db.query(Challenge).join(User, User.id == Challenge.creator_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        base = base.filter(or_(
            Challenge.title.ilike(like),
            Challenge.description.ilike(like),
            User.name.ilike(like),
        ))

    base = apply_filters(base)
    base = apply_sorting(base)

    rows: List[Challenge] = (
        base.offset((page - 1) * page_size).limit(page_size).all()
    )
    matched = [ChallengeItem.model_validate(ch) for ch in rows]
    matched_ids = {ch.id for ch in rows}

    predicted_tag = None
    predicted_score = None
    recommended: List[ChallengeItem] = []
    try:
        if q and q.strip():
            tag_name, score = predict_category(q.strip())
            predicted_tag = tag_name
            predicted_score = float(score) if score is not None else None

            tag_obj = db.query(Tag).filter(Tag.tag == tag_name, Tag.is_active == True).first()
            if tag_obj:
                rec = (db.query(Challenge)
                       .join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
                       .filter(ChallengeTag.tag_id == tag_obj.id)
                       .filter(~Challenge.id.in_(matched_ids)))
                rec = apply_filters(rec)
                rec = apply_sorting(rec)
                recommended = [ChallengeItem.model_validate(ch) for ch in rec.all()]
    except Exception:
        pass

    return DualSearchResponse(
        query=(q or ""),
        matched_challenges=matched,
        recommended_by_tag_challenges=recommended,
        predicted_tag=predicted_tag,
        predicted_score=predicted_score,
    )

# -------------------------------------------------------------------
# Create / List / Get / Update / Delete / Status
# -------------------------------------------------------------------
@router.post("/", response_model=ChallengeResponseWithTags)
async def create_challenge(
    challenge_data: ChallengeCreate,
    db: Session = Depends(get_db),
    tags: Optional[List[str]] = Body(None, embed=True),
):
    me = get_current_user_id()
    _validate_common_business_rules(
        challenge_data.start_date, challenge_data.end_date,
        challenge_data.fee, challenge_data.participation_fee,
    )
    if challenge_data.use_reward and not challenge_data.reward:
        raise HTTPException(400, "Reward content is required when use_reward is True")

    # (스키마에서 검증되지만) 서버 방어 로직 한 번 더
    if challenge_data.total_rounds is not None and challenge_data.total_rounds > 50:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "total_rounds cannot exceed 50")

    new_challenge = Challenge(
        title=challenge_data.title,
        description=challenge_data.description,
        start_date=challenge_data.start_date,
        end_date=challenge_data.end_date,
        creator_id=me,
        fee=challenge_data.fee or 0,
        participation_fee=challenge_data.participation_fee or 0,
        min_participants=challenge_data.min_participants,
        max_participants=challenge_data.max_participants,
        total_rounds=challenge_data.total_rounds,
        min_participation_rate=challenge_data.min_participation_rate or 80,
        max_participation_rate=challenge_data.max_participation_rate,
        mode=(challenge_data.mode.value if hasattr(challenge_data.mode, "value") else challenge_data.mode),
        same_place_for_all_rounds=challenge_data.same_place_for_all_rounds or False,
        default_zoom_link=challenge_data.default_zoom_link,
        default_place_name=challenge_data.default_place_name,
        default_road_address=challenge_data.default_road_address,
        default_address=challenge_data.default_address,
        default_map_url=challenge_data.default_map_url,
        default_latitude=challenge_data.default_latitude,
        default_longitude=challenge_data.default_longitude,
        default_place_id=getattr(challenge_data, 'default_place_id', None),
        use_reward=challenge_data.use_reward or False,
        reward=challenge_data.reward,
        cover_image_url=getattr(challenge_data, 'cover_image_url', None),
    )
    db.add(new_challenge)
    db.flush()

    # 태그 연결
    if tags:
        for tag_text in tags:
            t = db.query(Tag).filter(Tag.tag == tag_text).first()
            if not t:
                t = Tag(tag=tag_text, is_active=True)
                db.add(t)
                db.flush()
            exists = (
                db.query(ChallengeTag)
                .filter(ChallengeTag.challenge_id == new_challenge.id, ChallengeTag.tag_id == t.id)
                .first()
            )
            if not exists:
                db.add(ChallengeTag(challenge_id=new_challenge.id, tag_id=t.id))

    # 회차 자동 생성
    await auto_create_rounds_on_challenge_create(db, new_challenge)

    db.commit()
    db.refresh(new_challenge)
    return _with_tags(db, new_challenge)

@router.post("/{challenge_id}/cover-from-round-picture")
def set_cover_from_round_picture(
    challenge_id: int,
    round_picture_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not _can_edit_challenge(db, challenge_id, me):
        raise HTTPException(403, "No permission to edit cover")

    pic = (
        db.query(RoundPicture)
        .join(ChallengeRound, ChallengeRound.id == RoundPicture.round_id)
        .filter(ChallengeRound.challenge_id == challenge_id, RoundPicture.id == round_picture_id)
        .first()
    )
    if not pic:
        raise HTTPException(404, "Round picture not found in this challenge")

    ch.cover_round_picture_id = pic.id
    ch.cover_image_url = pic.file_url
    db.commit()
    db.refresh(ch)
    return {"message": "Cover image updated from round picture", "cover_image_url": ch.cover_image_url}

@router.post("/{challenge_id}/cover-url")
def set_cover_by_url(
    challenge_id: int,
    url: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not _can_edit_challenge(db, challenge_id, me):
        raise HTTPException(403, "No permission to edit cover")
    ch.cover_image_url = (url or '').strip() or None
    ch.cover_round_picture_id = None
    db.commit()
    return {"message": "Cover image updated", "cover_image_url": ch.cover_image_url}

@router.get("/", response_model=List[ChallengeResponseWithTags])
def list_challenges(db: Session = Depends(get_db)):
    rows = db.query(Challenge).all()
    out = []
    today = date.today()
    for ch in rows:
        ch.status = _calculate_status(ch, db, today)
        out.append(_with_tags(db, ch))
    return out

@router.get("/active", response_model=List[ChallengeResponseWithTags])
def get_active_challenges(db: Session = Depends(get_db)):
    rows = db.query(Challenge).filter(Challenge.status == "active").all()
    return [_with_tags(db, ch) for ch in rows]

@router.get("/status/{status}", response_model=List[ChallengeResponseWithTags])
def get_challenges_by_status(status: ChallengeStatus, db: Session = Depends(get_db)):
    rows = db.query(Challenge).filter(Challenge.status == status.value).all()
    return [_with_tags(db, ch) for ch in rows]

@router.get("/{challenge_id}", response_model=ChallengeResponseWithTags)
def get_challenge(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    ch.status = _calculate_status(ch, db, date.today())
    return _with_tags(db, ch)

@router.put("/{challenge_id}", response_model=ChallengeResponseWithTags)
def update_challenge(
    challenge_id: int,
    challenge_update: ChallengeUpdate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
    force: bool = Query(False, description="총회차 축소 시 의존데이터 있어도 강제 삭제"),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not _can_edit_challenge(db, challenge_id, me):
        raise HTTPException(403, "No permission to update this challenge")

    _validate_common_business_rules(
        challenge_update.start_date or ch.start_date,
        challenge_update.end_date or ch.end_date,
        challenge_update.fee if challenge_update.fee is not None else ch.fee,
        (challenge_update.participation_fee if challenge_update.participation_fee is not None else ch.participation_fee),
    )
    if challenge_update.use_reward is True and not (
        (challenge_update.reward is not None and str(challenge_update.reward).strip()) or ch.reward
    ):
        raise HTTPException(400, "Reward content is required when use_reward is True")

    before_total = ch.total_rounds
    data = challenge_update.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ch, k, v)
    db.flush()

    if "total_rounds" in data and data["total_rounds"] is not None and data["total_rounds"] != before_total:
        _reconcile_total_rounds(db, ch, data["total_rounds"], force=force)

    db.commit()
    db.refresh(ch)
    ch.status = _calculate_status(ch, db, date.today())
    return _with_tags(db, ch)

@router.delete("/{challenge_id}")
def delete_challenge(challenge_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can delete this challenge")

    participants = db.query(Participation).filter(Participation.challenge_id == challenge_id).count()
    if participants > 0:
        raise HTTPException(400, "Cannot delete challenge with participants")

    db.delete(ch)
    db.commit()
    return {"message": "Challenge deleted successfully"}

@router.patch("/{challenge_id}/status")
def update_challenge_status(challenge_id: int, new_status: ChallengeStatus, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can change challenge status")
    if ch.status == "completed":
        raise HTTPException(400, "Cannot change status of completed challenge")
    ch.status = new_status.value
    db.commit()
    db.refresh(ch)
    return {"message": f"Challenge status updated to {new_status.value}", "challenge": _with_tags(db, ch)}

# -------------------------------------------------------------------
# Rounds
# -------------------------------------------------------------------
@router.get("/{challenge_id}/rounds", response_model=List[ChallengeRoundResponse])
def get_challenge_rounds(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    rows = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id)
        .order_by(ChallengeRound.round)
        .all()
    )
    if not rows:
        return []
    ids = [r.id for r in rows]
    counts = dict(
        db.query(RoundAttendance.round_id, func.count())
        .filter(RoundAttendance.round_id.in_(ids), RoundAttendance.status == "pending")
        .group_by(RoundAttendance.round_id)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            ChallengeRoundResponse.model_validate(
                {
                    "id": r.id,
                    "challenge_id": r.challenge_id,
                    "mode": r.mode,
                    "round": r.round,
                    "processing_at": r.processing_at,
                    "start_time": r.start_time,
                    "finish_time": r.finish_time,
                    "description": r.description,
                    "url": r.url,
                    "place_name": r.place_name,
                    "road_address": r.road_address,
                    "address": r.address,
                    "map_url": r.map_url,
                    "lat": float(r.lat) if r.lat is not None else None,
                    "lon": float(r.lon) if r.lon is not None else None,
                    "geofence_radius_m": r.geofence_radius_m,
                    "zoom_meeting_id": r.zoom_meeting_id,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                    "planned_count": counts.get(r.id, 0),
                }
            )
        )
    return out

@router.post("/{challenge_id}/rounds", response_model=ChallengeRoundResponse)
def create_challenge_round(
    challenge_id: int,
    round_data: ChallengeRoundCreate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not can_edit_round(db, challenge_id, None, me):
        raise HTTPException(403, "No permission to create rounds for this challenge.")
    dup = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.round == round_data.round)
        .first()
    )
    if dup:
        raise HTTPException(400, "Round number already exists")
    new_round = ChallengeRound(
        challenge_id=challenge_id,
        mode=(round_data.mode.value if hasattr(round_data.mode, "value") else round_data.mode),
        round=round_data.round,
        processing_at=round_data.processing_at,
        start_time=round_data.start_time,
        finish_time=round_data.finish_time,
        description=round_data.description,
        url=round_data.url,
        place_name=round_data.place_name,
        road_address=round_data.road_address,
        address=round_data.address,
        map_url=getattr(round_data, "map_url", None),
        lat=round_data.lat,
        lon=round_data.lon,
        geofence_radius_m=round_data.geofence_radius_m,
        zoom_meeting_id=round_data.zoom_meeting_id,
    )
    db.add(new_round)
    db.commit()
    db.refresh(new_round)
    return new_round

@router.get("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def get_challenge_round(challenge_id: int, round_id: int, db: Session = Depends(get_db)):
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    return r

@router.put("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def update_challenge_round(
    challenge_id: int,
    round_id: int,
    round_update: ChallengeRoundUpdate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    if not can_edit_round(db, challenge_id, round_id, me):
        raise HTTPException(403, "No permission to edit this round.")

    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()

    data = round_update.model_dump(exclude_unset=True)

    # mode 변경은 hybrid에서만 허용
    if "mode" in data and data["mode"] is not None:
        data["mode"] = data["mode"].value if hasattr(data["mode"], "value") else data["mode"]
        if ch and ch.mode != "hybrid":
            raise HTTPException(400, "mode는 hybrid일 때만 변경 가능")

    # 공백 문자열은 None으로 정리
    for key in ("url", "map_url", "place_name", "road_address", "address", "description", "zoom_meeting_id"):
        if key in data and isinstance(data[key], str) and data[key].strip() == "":
            data[key] = None

    # 온라인 모드 + map_url만 온 경우 → url로 저장
    eff_mode = data.get("mode") or r.mode
    if eff_mode == "online" and "map_url" in data and data.get("map_url") and "url" not in data:
        data["url"] = data["map_url"]

    for k, v in data.items():
        setattr(r, k, v)

    db.commit()
    db.refresh(r)

    planned_count = (
        db.query(func.count())
        .select_from(RoundAttendance)
        .filter(RoundAttendance.round_id == r.id, RoundAttendance.status == "pending")
        .scalar()
    )
    return ChallengeRoundResponse.model_validate({**r.__dict__, "planned_count": planned_count})

@router.delete("/{challenge_id}/rounds/{round_id}")
def delete_challenge_round(
    challenge_id: int, round_id: int,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    if not can_edit_round(db, challenge_id, round_id, me):
        raise HTTPException(403, "No permission to delete this round.")
    if _round_has_dependents(r):
        raise HTTPException(409, "This round has dependent data and cannot be deleted.")

    db.delete(r)
    db.flush()

    remain = db.query(ChallengeRound).filter(ChallengeRound.challenge_id == challenge_id).count()
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if ch:
        ch.total_rounds = remain

    db.commit()
    return {"message": "Round deleted successfully", "total_rounds": remain}

# -------------------------------------------------------------------
# Participation / Attendees / Delegation
# -------------------------------------------------------------------
@router.post("/{challenge_id}/join")
def join_challenge(challenge_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.status != "recruiting":
        raise HTTPException(400, "Can only join recruiting challenges")
    exists = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == me, Participation.is_active == True)
        .first()
    )
    if exists:
        raise HTTPException(400, "Already joined this challenge")
    if ch.max_participants:
        cnt = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.is_active == True).count()
        if cnt >= ch.max_participants:
            raise HTTPException(400, "Challenge is full")
    db.add(Participation(challenge_id=challenge_id, user_id=me, role=ParticipationRole.participant))
    db.commit()
    return {"message": "Joined challenge successfully"}

@router.delete("/{challenge_id}/leave")
def leave_challenge(challenge_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    part = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == me)
        .first()
    )
    if not part:
        raise HTTPException(404, "Not a participant of this challenge")
    if ch.creator_id == me:
        raise HTTPException(400, "Creator cannot leave their own challenge. Delete the challenge instead.")
    if ch.status == "completed":
        raise HTTPException(400, "Cannot leave a completed challenge")
    db.delete(part)
    db.commit()
    return {"message": "You have left the challenge"}

@router.get("/{challenge_id}/participants")
def get_challenge_participants(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    parts = db.query(Participation).filter(Participation.challenge_id == challenge_id).all()
    users = {u.id: u for u in db.query(User).filter(User.id.in_([p.user_id for p in parts])).all()}
    return [
        {
            "user_id": p.user_id,
            "username": users.get(p.user_id).username if users.get(p.user_id) else "Unknown",
            "joined_at": p.joined_at,
            "status": p.status,
            "role": p.role.value if hasattr(p.role, "value") else p.role,
        }
        for p in parts
    ]

@router.get("/my", response_model=List[ChallengeResponseWithTags])
def get_my_challenges(db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ids = [cid for (cid,) in db.query(Participation.challenge_id).filter(Participation.user_id == me).all()]
    if not ids:
        return []
    rows = db.query(Challenge).filter(Challenge.id.in_(ids)).all()
    out = []
    today = date.today()
    for ch in rows:
        ch.status = _calculate_status(ch, db, today)
        out.append(_with_tags(db, ch))
    return out

@router.delete("/{challenge_id}/kick/{user_id}")
def kick_participant(challenge_id: int, user_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me and not is_challenge_manager(db, challenge_id, me):
        raise HTTPException(403, "No permission to kick participants")
    part = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id)
        .first()
    )
    if not part:
        raise HTTPException(404, "User not in challenge")
    db.delete(part)
    db.commit()
    return {"message": "User has been removed from the challenge"}

# RSVP / Attendees per round
@router.post("/{challenge_id}/rounds/{round_id}/attend")
def attend_round(challenge_id: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    joined = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == me, Participation.is_active == True)
        .first()
    )
    if not joined:
        raise HTTPException(403, "Join the challenge first.")
    r = db.query(ChallengeRound).filter(ChallengeRound.id == round_id, ChallengeRound.challenge_id == challenge_id).first()
    if not r:
        raise HTTPException(404, "Round not found")
    att = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == me).first()
    if att:
        att.status = "pending"
    else:
        db.add(RoundAttendance(user_id=me, round_id=round_id, status="pending"))
    db.commit()
    return {"message": "RSVP set to attending (pending)."}

@router.delete("/{challenge_id}/rounds/{round_id}/attend")
def unattend_round(challenge_id: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    att = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == me).first()
    if not att:
        return {"message": "Already not attending."}
    if not getattr(att, "is_checked_in", False) and not getattr(att, "checkin_time", None):
        db.delete(att)
    else:
        att.status = "absent"
    db.commit()
    return {"message": "RSVP removed."}

@router.post("/{challenge_id}/rounds/{round_id}/decline")
def decline_round_alias(challenge_id: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    return unattend_round(challenge_id, round_id, db, me)

@router.get("/{challenge_id}/rounds/{round_id}/attendees")
def get_round_attendees(challenge_id: int, round_id: int, planned_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id)
    if planned_only:
        q = q.filter(RoundAttendance.status == "pending")
    rows = q.all()
    ids = [r.user_id for r in rows]
    if not ids:
        return []
    users = db.query(User).filter(User.id.in_(ids)).all()
    u_map = {u.id: u for u in users}
    return [
        {
            "user_id": uid,
            "username": (u_map.get(uid).username if u_map.get(uid) else None),
            "name": (u_map.get(uid).name if u_map.get(uid) else None),
            "profile_image": (u_map.get(uid).profile_image if u_map.get(uid) else None),
        }
        for uid in ids
    ]

# Delegation (challenge owner only)
@router.post("/{challenge_id}/delegate")
def delegate_challenge(challenge_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only owner can delegate managers.")
    p = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id).first()
    if not p:
        p = Participation(challenge_id=challenge_id, user_id=user_id)
        db.add(p)
        db.flush()
    p.role = ParticipationRole.manager
    p.is_active = True
    db.commit()
    return {"message": f"user {user_id} is now manager of challenge {challenge_id}"}

@router.post("/{challenge_id}/undelegate")
def undelegate_challenge(challenge_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only owner can undelegate managers.")
    p = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id).first()
    if not p or p.role != ParticipationRole.manager:
        raise HTTPException(404, "Target user is not a manager.")
    p.role = ParticipationRole.participant
    db.commit()
    return {"message": f"user {user_id} manager revoked for challenge {challenge_id}"}

@router.post("/{challenge_id}/transfer")
def transfer_challenge(challenge_id: int, to_user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only owner can transfer ownership.")
    ch.creator_id = to_user_id
    db.commit()
    return {"message": f"challenge {challenge_id} transferred to user {to_user_id}"}

@router.post("/{challenge_id}/rounds/{round_id}/delegate-manager")
def delegate_round_manager(challenge_id: int, round_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only the creator can delegate a round manager.")
    r = db.query(ChallengeRound).filter(ChallengeRound.id == round_id, ChallengeRound.challenge_id == challenge_id).first()
    if not r:
        raise HTTPException(404, "Round not found")
    ra = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == user_id, RoundAttendance.status == "pending").first()
    if not ra:
        raise HTTPException(400, "Only planned attendees can be delegated.")
    existing = db.query(RoundManager).filter(RoundManager.challenge_id == challenge_id, RoundManager.round_id == round_id).first()
    if existing:
        existing.user_id = user_id
    else:
        db.add(RoundManager(challenge_id=challenge_id, round_id=round_id, user_id=user_id))
    db.commit()
    return {"message": f"user {user_id} is now manager for round {round_id}"}

@router.post("/{challenge_id}/rounds/{round_id}/undelegate-manager")
def undelegate_round_manager(challenge_id: int, round_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only the creator can revoke a round manager.")
    rm = db.query(RoundManager).filter(RoundManager.challenge_id == challenge_id, RoundManager.round_id == round_id, RoundManager.user_id == user_id).first()
    if not rm:
        raise HTTPException(404, "Round manager not found")
    db.delete(rm)
    db.commit()
    return {"message": f"user {user_id} is no longer manager for round {round_id}"}
