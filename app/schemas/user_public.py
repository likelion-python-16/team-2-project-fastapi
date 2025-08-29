from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserPublicOut(BaseModel):
    id: int
    username: str
    name: Optional[str] = ""
    is_active: Optional[bool] = True
    gender: Optional[str] = "other"
    region_living: Optional[str] = ""
    region_active: Optional[str] = ""
    profile_image: Optional[str] = ""
    introduction: Optional[str] = ""
    manner_score: Optional[float] = 0

    # Optional timestamps for context; safe to expose
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "username": "haru",
                "name": "하루",
                "is_active": True,
                "gender": "other",
                "region_living": "서울",
                "region_active": "경기",
                "profile_image": "https://.../avatar.png",
                "introduction": "안녕하세요!",
                "manner_score": 36.5,
                "created_at": "2025-08-13T12:00:00",
                "updated_at": "2025-08-17T10:00:00",
            }
        },
    )

