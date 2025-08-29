# app/services/challenge_round_service.py
from datetime import date, time, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.challenge import Challenge
from app.models.challenge_round import ChallengeRound
from app.services.naver_maps import geocode, build_naver_map_url

# 기본 시간(필요시 조정)
DEFAULT_START = time(9, 0, 0)    # 19:00 시작
DEFAULT_END   = time(21, 0, 0)    # 21:00 종료
DEFAULT_DESC  = "자동 생성 라운드"  # description NOT NULL 방지용 기본값


def _compute_processing_date(challenge: Challenge, index_one_based: int) -> date:
    """
    processing_at(날짜)을 계산한다. (타입: datetime.date)
    - start_date가 있으면: start_date + (i-1)일
    - start_date가 없고 end_date만 있으면: end_date - (n-i)일
    - 둘 다 없으면: 오늘 + (i-1)일
    """
    n = challenge.total_rounds or 1
    i = max(1, index_one_based)

    if challenge.start_date:
        return challenge.start_date + timedelta(days=i - 1)

    if challenge.end_date:
        return challenge.end_date - timedelta(days=(n - i))

    return date.today() + timedelta(days=i - 1)


async def auto_create_rounds_on_challenge_create(db: Session, challenge: Challenge):
    n = challenge.total_rounds or 0
    if n <= 0:
        return
    # ✅ 방어 로직: 최대 50회
    if n > 50:
        raise HTTPException(status_code=422, detail="total_rounds cannot exceed 50")

    lat = lon = None
    road = challenge.default_road_address
    addr = challenge.default_address
    pname = challenge.default_place_name
    place_id = getattr(challenge, 'default_place_id', None)
    map_url = None
    same_all = bool(getattr(challenge, 'same_place_for_all_rounds', False))

    if same_all and pname and (challenge.mode in ('offline','hybrid')):
        geo = await geocode(road)
        if geo:
            lat, lon = geo["lat"], geo["lng"]
            addr = addr or geo.get("address")
            road = geo.get("road_address") or road
            # placeId가 있으면 entry/place 링크로, 없으면 좌표 기반 링크
            if place_id:
                # 좌표가 있으면 지도 센터 고정
                c = f"?c={lon},{lat},15,0,0,0,dh" if (lat is not None and lon is not None) else ''
                map_url = f"https://map.naver.com/v5/entry/place/{place_id}{c}"
            else:
                map_url = build_naver_map_url(pname, lat, lon, None)

    for i in range(1, n + 1):
        processing_at = _compute_processing_date(challenge, i)

        r = ChallengeRound(
            challenge_id=challenge.id,
            round=i,
            mode=(
                'online' if challenge.mode == 'online'
                else 'offline' if challenge.mode == 'offline'
                else ('offline' if (same_all and map_url is not None) else 'online')
            ),
            processing_at=processing_at,
            start_time=DEFAULT_START,
            finish_time=DEFAULT_END,
            description=f"{DEFAULT_DESC} #{i}",
        )

        if r.mode == 'online':
            r.url = challenge.default_zoom_link or None
        elif r.mode == 'offline' and lat is not None and lon is not None:
            r.place_name = pname
            r.road_address = road
            r.address = addr
            r.lat = lat
            r.lon = lon
            r.map_url = map_url

        db.add(r)

    db.flush()


def _round_has_dependent_data(r: ChallengeRound) -> bool:
    return bool(
        (r.attendances and len(r.attendances) > 0) or
        (r.proofs and len(r.proofs) > 0) or
        (r.qrcodes and len(r.qrcodes) > 0) or
        (r.reviews and len(r.reviews) > 0)
    )


def reconcile_total_rounds(db: Session, challenge: Challenge, new_total: int, force: bool = False):
    if new_total > 50:
        raise HTTPException(status_code=422, detail="total_rounds cannot exceed 50")

    current = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge.id
    ).order_by(ChallengeRound.round.asc()).all()

    cur_n = len(current)
    if new_total == cur_n:
        return

    # 늘리는 경우
    if new_total > cur_n:
        for i in range(cur_n + 1, new_total + 1):
            processing_at = _compute_processing_date(challenge, i)
            r = ChallengeRound(
                challenge_id=challenge.id,
                round=i,
                mode=('online' if challenge.mode == 'online'
                      else 'offline' if challenge.mode == 'offline'
                      else 'online'),
                processing_at=processing_at,
                start_time=DEFAULT_START,
                finish_time=DEFAULT_END,
                description=f"{DEFAULT_DESC} #{i}",
            )
            if challenge.mode == 'online':
                r.url = challenge.default_zoom_link or None
            db.add(r)
        db.flush()
        return

    # 줄이는 경우
    to_delete = [r for r in current if r.round > new_total]
    for r in reversed(to_delete):
        if _round_has_dependent_data(r) and not force:
            raise HTTPException(status_code=409, detail=f"Round {r.round} has dependent data")
        db.delete(r)
    db.flush()
