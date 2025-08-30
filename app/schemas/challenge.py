# app/schemas/challenge.py
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Annotated, Any, Dict

from pydantic import BaseModel, ConfigDict, field_validator, model_validator, Field


# -----------------------------
# Enums
# -----------------------------
class ChallengeMode(str, Enum):
    online = "online"
    offline = "offline"
    hybrid = "hybrid"


class ChallengeStatus(str, Enum):
    RECRUITING = "recruiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

RoundCount = Annotated[int, Field(ge=1, le=100)]


# -----------------------------
# Create / Update
# -----------------------------
def _map_korean_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data
    # 한글 → 영문 키 매핑
    alias = {
        "수수료": "fee",
        "참가비": "participation_fee",
        "최소 참가 인원": "min_participants",
        "최대 참가 인원": "max_participants",
        "총 라운드": "total_rounds",
        "최소 참가율": "min_participation_rate",
        "최대 참가율": "max_participation_rate",
        "모드": "mode",
        "기본 줌 링크": "default_zoom_link",
        "모든 라운드에 동일한 장소": "same_place_for_all_rounds",
        "모든 회차 동일 장소": "same_place_for_all_rounds",
        "기본 장소 이름": "default_place_name",
        "기본 도로 주소": "default_road_address",
        "기본 주소": "default_address",
        "기본 지도 URL": "default_map_url",
        "기본 위도": "default_latitude",
        "기본 경도": "default_longitude",
        "기본 장소 ID": "default_place_id",
        "태그": "tags",
        "커버 이미지 URL": "cover_image_url",
        # 호환 키(일부 응답/클라이언트에서 혼용 가능)
        "cover": "cover_image_url",
        "coverUrl": "cover_image_url",
    }
    out = dict(data)
    for k_kr, k_en in alias.items():
        if k_kr in out and k_en not in out:
            out[k_en] = out.pop(k_kr)

    # 모드 값 한/영 치환
    mode = out.get("mode")
    if isinstance(mode, str):
        m = mode.strip().lower()
        map_mode = {
            "온라인": "online",
            "오프라인": "offline",
            "하이브리드": "hybrid",
            "온오프라인": "hybrid",
        }
        out["mode"] = map_mode.get(mode, map_mode.get(m, mode))

    # 불리언 텍스트 보정 (예: "true"/"false")
    def to_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            vv = v.strip().lower()
            if vv in ("true", "1", "yes", "y"): return True
            if vv in ("false", "0", "no", "n"): return False
        return v
    for key in ("same_place_for_all_rounds", "use_reward"):
        if key in out:
            out[key] = to_bool(out[key])

    return out


class ChallengeCreate(BaseModel):
    # 기본 정보
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # 요금
    fee: Optional[int] = 0
    participation_fee: Optional[int] = 0

    # 참가 인원
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None

    # 회차/참여율
    total_rounds: Optional[RoundCount] = None
    min_participation_rate: Optional[int] = 80
    max_participation_rate: Optional[int] = None

    # 리워드
    use_reward: Optional[bool] = False
    reward: Optional[str] = None

    # 모드/기본 링크
    mode: ChallengeMode = ChallengeMode.hybrid
    default_zoom_link: Optional[str] = None

    # 장소(모든 회차 동일 옵션 + 기본 장소 정보)
    same_place_for_all_rounds: Optional[bool] = False
    default_place_name: Optional[str] = None
    default_road_address: Optional[str] = None
    default_address: Optional[str] = None
    default_map_url: Optional[str] = None
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_place_id: Optional[str] = None

    # 대표 이미지 URL (선택)
    cover_image_url: Optional[str] = None

    # 태그(카테고리)
    tags: Optional[List[str]] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="ignore",
        json_schema_extra={
            "example": {
                "title": "배드민턴 챌린지",
                "description": "주 3회 운동",
                "start_date": "2025-08-19",
                "end_date": "2025-08-27",
                "fee": 0,
                "participation_fee": 5000,
                "min_participants": 2,
                "max_participants": 10,
                "total_rounds": 5,
                "min_participation_rate": 80,
                "mode": "hybrid",
                "default_zoom_link": None,
                "same_place_for_all_rounds": True,
                "default_place_name": "탄천종합운동장",
                "default_road_address": "경기도 성남시 분당구 탄천로 215",
                "default_address": "경기도 성남시 분당구 야탑동 486",
                "default_map_url": "https://map.naver.com/v5/entry/place/12345",
                "default_latitude": 37.1234,
                "default_longitude": 127.1234,
                "tags": ["운동/스포츠"],
            }
        },
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        if len(v.strip()) < 2:
            raise ValueError("Title must be at least 2 characters long")
        return v.strip()

    @field_validator("participation_fee")
    @classmethod
    def validate_participation_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v > 10000:
            raise ValueError("Participation fee cannot exceed 10,000 KRW")
        if v is not None and v < 0:
            raise ValueError("Participation fee cannot be negative")
        return v

    @field_validator("fee")
    @classmethod
    def validate_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Fee cannot be negative")
        return v

    @field_validator("min_participation_rate")
    @classmethod
    def validate_min_rate(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Participation rate must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def validate_cross_fields(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be ≤ end_date")

        if (
            self.max_participation_rate is not None
            and self.min_participation_rate is not None
            and self.max_participation_rate < self.min_participation_rate
        ):
            raise ValueError("max_participation_rate must be ≥ min_participation_rate")

        if self.use_reward and not (self.reward and self.reward.strip()):
            raise ValueError("Reward content is required when use_reward is True")

        # 정책 선택지:
        # fee/pfee 둘 다 허용 (현재 유지)
        # if (fee > 0 and pfee > 0) or (fee == 0 and pfee == 0): ...
        return self

    # ✅ 요청 바인딩 직전: 한글 키/값 보정, 불필요 키 무시
    @model_validator(mode="before")
    @classmethod
    def _korean_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _map_korean_keys(data)
        return data


class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[ChallengeStatus] = None

    fee: Optional[int] = None
    participation_fee: Optional[int] = None
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None
    total_rounds: Optional[RoundCount] = None
    min_participation_rate: Optional[int] = None
    max_participation_rate: Optional[int] = None

    use_reward: Optional[bool] = None
    reward: Optional[str] = None

    mode: Optional[ChallengeMode] = None
    default_zoom_link: Optional[str] = None

    same_place_for_all_rounds: Optional[bool] = None
    default_place_name: Optional[str] = None
    default_road_address: Optional[str] = None
    default_address: Optional[str] = None
    default_map_url: Optional[str] = None
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_place_id: Optional[str] = None

    tags: Optional[List[str]] = None
    cover_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="ignore")

    @field_validator("participation_fee")
    @classmethod
    def validate_participation_fee_u(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v > 10000:
            raise ValueError("Participation fee cannot exceed 10,000 KRW")
        if v is not None and v < 0:
            raise ValueError("Participation fee cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_cross_fields(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be ≤ end_date")

        if self.min_participation_rate is not None and not (0 <= self.min_participation_rate <= 100):
            raise ValueError("min_participation_rate must be 0..100")
        if self.max_participation_rate is not None and not (0 <= self.max_participation_rate <= 100):
            raise ValueError("max_participation_rate must be 0..100")
        if (
            self.min_participation_rate is not None
            and self.max_participation_rate is not None
            and self.max_participation_rate < self.min_participation_rate
        ):
            raise ValueError("max_participation_rate must be ≥ min_participation_rate")

        if self.use_reward is True and (self.reward is None or self.reward.strip() == ""):
            raise ValueError("Reward content is required when use_reward is True")

        # 정책 선택지:
        # 둘 다 양수/둘 다 0 금지하려면 아래 활성화
        # if self.fee is not None and self.participation_fee is not None:
        #     fee = int(self.fee or 0)
        #     pfee = int(self.participation_fee or 0)
        #     if (fee > 0 and pfee > 0) or (fee == 0 and pfee == 0):
        #         raise ValueError("Exactly one of fee or participation_fee must be > 0")

        return self

    # ✅ 요청 바인딩 직전: 한글 키/값 보정
    @model_validator(mode="before")
    @classmethod
    def _korean_aliases_u(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _map_korean_keys(data)
        return data


# -----------------------------
# Read Models
# -----------------------------
class ChallengeOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: ChallengeStatus = ChallengeStatus.RECRUITING
    created_at: datetime
    updated_at: Optional[datetime] = None

    fee: int
    participation_fee: int
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None
    total_rounds: Optional[int] = None
    min_participation_rate: int
    max_participation_rate: Optional[int] = None

    use_reward: bool
    reward: Optional[str] = None
    is_closed: bool
    is_deleted: bool

    mode: ChallengeMode
    default_zoom_link: Optional[str] = None

    same_place_for_all_rounds: Optional[bool] = None
    default_place_name: Optional[str] = None
    default_road_address: Optional[str] = None
    default_address: Optional[str] = None
    default_map_url: Optional[str] = None
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_place_id: Optional[str] = None

    tags: Optional[List[str]] = None
    cover_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChallengeResponse(ChallengeOut):
    pass


class ChallengeItem(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int
    status: str  # string으로 두면 Enum/str 모두 수용
    start_date: date
    end_date: date
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DualSearchResponse(BaseModel):
    query: str
    matched_challenges: List[ChallengeItem] = []
    recommended_by_tag_challenges: List[ChallengeItem] = []
    predicted_tag: Optional[str] = None
    predicted_score: Optional[float] = None
