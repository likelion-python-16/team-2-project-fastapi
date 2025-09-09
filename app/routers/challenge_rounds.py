from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.challenge import Challenge
from app.models.challenge_round import ChallengeRound
from app.services.naver_maps import geocode, build_naver_map_url

async def auto_create_rounds_on_challenge_create(db: Session, challenge: Challenge):
    n = challenge.total_rounds or 0
    if n <= 0:
        return

    lat = lon = None
    road = challenge.default_road_address
    addr = challenge.default_address
    pname = challenge.default_place_name
    map_url = None
    same_all = bool(getattr(challenge, 'same_place_for_all_rounds', False))

    if challenge.mode == 'offline' and same_all and road and pname:
        geo = await geocode(road)
        if geo:
            lat, lon = geo["lat"], geo["lng"]
            addr = addr or geo.get("address")
            road = geo.get("road_address") or road
            map_url = build_naver_map_url(pname, lat, lon, getattr(challenge, 'default_place_id', None))

    for i in range(1, n + 1):
        r = ChallengeRound(
            challenge_id=challenge.id,
            round=i,
            mode=('online' if challenge.mode=='online'
                  else 'offline' if challenge.mode=='offline'
                  else 'online'),  # hybrid이면 우선 online; 이후 회차 수정에서 변경
        )
        if challenge.mode == 'online':
            r.url = challenge.default_zoom_link
        elif challenge.mode == 'offline' and lat is not None and lon is not None:
            r.place_name = pname
            r.road_address = road
            r.lat = lat; r.lon = lon
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
    current = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge.id
    ).order_by(ChallengeRound.round.asc()).all()

    cur_n = len(current)
    if new_total == cur_n:
        return

    if new_total > cur_n:
        for i in range(cur_n + 1, new_total + 1):
            r = ChallengeRound(
                challenge_id=challenge.id,
                round=i,
                mode='online' if challenge.mode=='online' else 'offline' if challenge.mode=='offline' else 'online'
            )
            if challenge.mode == 'online':
                r.url = challenge.default_zoom_link
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
