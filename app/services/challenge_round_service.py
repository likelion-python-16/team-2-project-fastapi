# app/services/challenge_round_service.py

from datetime import date, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.challenge import Challenge, ChallengeMode
from app.models.challenge_round import ChallengeRound
from app.services.naver_maps import geocode, build_naver_map_url

# 기본 시간(필요시 조정)
DEFAULT_START = time(19, 0, 0)    # 19:00 시작
DEFAULT_END   = time(21, 0, 0)    # 21:00 종료
DEFAULT_DESC  = "자동 생성 라운드"   # description NOT NULL 방지용 기본값


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


# --- Round.mode 안전 변환 유틸 (Round에 Enum이 있든 없든 동작) ---
def _to_round_mode(value: str):
    """
    ChallengeRound.mode 컬럼이:
      - 문자열(String)인 경우: 그대로 문자열 반환
      - Enum(SAEnum)인 경우: 동일 값의 Enum으로 변환
    """
    # Round 모듈에 Enum이 정의돼 있으면 사용 (예: RoundMode)
    RM = getattr(__import__("app.models.challenge_round", fromlist=["*"]), "RoundMode", None)
    if RM is not None:
        try:
            return RM(value)
        except Exception:
            # Fallback: 첫 값 사용
            return list(RM)[0]
    # 문자열 컬럼일 때
    return value


async def auto_create_rounds_on_challenge_create(db: Session, challenge: Challenge):
    """
    챌린지 생성 시 total_rounds 만큼 회차를 자동 생성.
    - offline + same_place_for_all_rounds + 기본 장소 정보가 있을 때만 1회 지오코딩
    - 이미 default_latitude/longitude가 있으면 지오코딩 생략
    """
    n = challenge.total_rounds or 0
    if n <= 0:
        return

    # 우선 기본 좌표 사용 (있으면 지오코딩 스킵)
    lat: Optional[float] = getattr(challenge, "default_latitude", None)
    lon: Optional[float] = getattr(challenge, "default_longitude", None)
    road = getattr(challenge, "default_address", None)           # ✅ 모델에 맞춤
    addr = getattr(challenge, "default_address", None)           # 굳이 나눌 필요 없으면 동일 사용
    pname = getattr(challenge, "default_place_name", None)
    map_url = None
    same_all = bool(getattr(challenge, "same_place_for_all_rounds", False))

    # Enum → 문자열
    ch_mode_str = challenge.mode.value if hasattr(challenge.mode, "value") else str(challenge.mode)

    # 오프라인 + 모든 회차 동일 장소 + 기본 장소 정보가 있고 + 위경도가 없다면 → 1회 지오코딩
    if (
        challenge.mode == ChallengeMode.offline
        and same_all
        and pname
        and road
        and (lat is None or lon is None)
    ):
        geo = await geocode(road)
        if geo:
            lat = geo.get("lat")
            lon = geo.get("lng")
            # 주소 보정 (있을 때)
            addr = addr or geo.get("address")
            road = geo.get("road_address") or road

    # 지도 링크 만들기 (좌표가 있으면 마커 보장)
    if challenge.mode == ChallengeMode.offline and same_all and pname and (lat is not None and lon is not None):
        map_url = build_naver_map_url(pname, lat, lon, None)

    for i in range(1, n + 1):
        processing_at = _compute_processing_date(challenge, i)  # ✅ Date 타입

        # hybrid이면 기본 online으로 시작 (이후 라운드 개별 수정에서 오프라인으로 전환 가능)
        per_round_mode_str = (
            "online" if challenge.mode in (ChallengeMode.online, ChallengeMode.hybrid) else "offline"
        )

        r = ChallengeRound(
            challenge_id=challenge.id,
            round=i,
            mode=_to_round_mode(per_round_mode_str),  # ✅ Round Enum/문자열 모두 호환
            processing_at=processing_at,              # NOT NULL
            start_time=DEFAULT_START,                 # NOT NULL (Time)
            finish_time=DEFAULT_END,                  # NOT NULL (Time)
            description=f"{DEFAULT_DESC} #{i}",      # NOT NULL (Text)
        )

        # 온라인 → 기본 링크
        if challenge.mode == ChallengeMode.online:
            r.url = getattr(challenge, "default_zoom_link", None) or None

        # 오프라인 + 동일 장소 → 계산된 장소/좌표 일괄 복사
        elif challenge.mode == ChallengeMode.offline and same_all and (lat is not None and lon is not None):
            r.place_name = pname
            r.road_address = road
            r.address = addr
            # Round 모델의 필드명이 lat/lon 혹은 latitude/longitude일 수 있음 → 둘 다 채우기 시도
            if hasattr(r, "lat"):
                r.lat = lat
            if hasattr(r, "lon"):
                r.lon = lon
            if hasattr(r, "latitude"):
                r.latitude = lat
            if hasattr(r, "longitude"):
                r.longitude = lon
            r.map_url = map_url

        db.add(r)

    db.flush()


def _round_has_dependent_data(r: ChallengeRound) -> bool:
    return bool(
        (getattr(r, "attendances", None) and len(r.attendances) > 0) or
        (getattr(r, "proofs", None) and len(r.proofs) > 0) or
        (getattr(r, "qrcodes", None) and len(r.qrcodes) > 0) or
        (getattr(r, "reviews", None) and len(r.reviews) > 0)
    )


def reconcile_total_rounds(db: Session, challenge: Challenge, new_total: int, force: bool = False):
    """
    total_rounds 변경 시 실제 회차 테이블과 동기화
    - 늘릴 때: 필수 필드 채워서 생성
    - 줄일 때: 의존 데이터 있으면 409 (force=True 시 강제 삭제)
    """
    current = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge.id)
        .order_by(ChallengeRound.round.asc())
        .all()
    )

    cur_n = len(current)
    if new_total == cur_n:
        return

    # 늘리기
    if new_total > cur_n:
        for i in range(cur_n + 1, new_total + 1):
            processing_at = _compute_processing_date(challenge, i)

            per_round_mode_str = (
                "online" if challenge.mode in (ChallengeMode.online, ChallengeMode.hybrid) else "offline"
            )

            r = ChallengeRound(
                challenge_id=challenge.id,
                round=i,
                mode=_to_round_mode(per_round_mode_str),
                processing_at=processing_at,
                start_time=DEFAULT_START,
                finish_time=DEFAULT_END,
                description=f"{DEFAULT_DESC} #{i}",
            )
            if challenge.mode == ChallengeMode.online:
                r.url = getattr(challenge, "default_zoom_link", None) or None

            db.add(r)
        db.flush()
        return

    # 줄이기
    to_delete = [r for r in current if r.round > new_total]
    for r in reversed(to_delete):
        if _round_has_dependent_data(r) and not force:
            raise HTTPException(status_code=409, detail=f"Round {r.round} has dependent data")
        db.delete(r)
    db.flush()
