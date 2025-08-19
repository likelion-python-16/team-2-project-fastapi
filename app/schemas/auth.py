from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic.config import ConfigDict
from typing import Optional, List
from datetime import datetime, date
import re

# -----------------------------
# 회원가입 요청 스키마 (Pydantic v2)
# -----------------------------
class SignUpIn(BaseModel):
    # ---- 계정 기본 ----
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)")
    name: Optional[str] = Field(None, max_length=100, description="실명 (선택사항)")

    # ---- 필수 확장 항목 ----
    address_text: str = Field(..., description="주소(자동완성 결과나 자유입력)")
    phone: str = Field(..., description="전화번호(10~15자리, 숫자/-,+ 허용)")
    region_living: str = Field(..., description="거주 지역(예: 서울특별시 강남구)")
    region_active: str = Field(..., description="주 활동 지역(검색 최적화용)")
    tags: List[str] = Field(..., description="관심 태그(최소 3개, 중복 제거)")

    # ---- 선택 항목 ----
    identification_number: Optional[str] = Field(None, description="식별번호(서버에서 암호화 저장)")
    gender: Optional[str] = Field(None, description="성별(M/F/OTHER)")
    birth_date: Optional[date] = Field(None, description="생년월일 YYYY-MM-DD")
    profile_image: Optional[str] = Field(None, description="프로필 이미지 URL")
    introduction: Optional[str] = Field(None, max_length=1000, description="자기소개")

    # --- validators (Pydantic v2) ---
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v:
            raise ValueError('사용자명은 필수입니다')
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            raise ValueError('사용자명은 영문으로 시작, 영문/숫자/_만 사용 가능합니다')
        return v.lower()

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v2 = v.strip()
        if not v2:
            return None
        if len(v2) < 2:
            raise ValueError('실명은 2자 이상이어야 합니다')
        return v2

    @field_validator('identification_number')
    @classmethod
    def validate_identification_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v2 = v.replace('-', '')
        if not re.match(r'^\d{13}$', v2):
            raise ValueError('식별번호는 13자리 숫자여야 합니다')
        if v2[6] not in ['1', '2', '3', '4']:
            raise ValueError('올바르지 않은 식별번호 형식입니다')
        return v2

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 시작은 숫자/+, 이후 숫자 또는 -를 9~14개 → 총 길이 10~15 허용
        if not re.match(r'^[0-9+][0-9\-]{9,14}$', v):
            raise ValueError('전화번호 형식이 올바르지 않습니다 (10~15자, 숫자/-,+ 허용)')
        return v

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.upper()
        if vv not in {'M', 'F', 'OTHER'}:
            raise ValueError('gender는 M/F/OTHER 중 하나여야 합니다')
        return vv

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        # 공백 제거 + 빈값 제거 + 순서 유지 중복 제거
        uniq = [t.strip() for t in v if t and t.strip()]
        uniq = list(dict.fromkeys(uniq))
        if len(uniq) < 3:
            raise ValueError('관심 태그는 최소 3개 이상이어야 합니다')
        return uniq

    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        if v > date.today():
            raise ValueError('생년월일은 미래일 수 없습니다')
        return v

# -----------------------------
# 로그인 요청 스키마 (Pydantic v2)
# -----------------------------
class LoginIn(BaseModel):
    login: str = Field(..., description="사용자명 또는 이메일")
    password: str = Field(..., description="비밀번호")

    @field_validator('login')
    @classmethod
    def validate_login(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자명 또는 이메일을 입력해주세요')
        return v.strip()

    # v2: Config → model_config / json_schema_extra
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "login": "johndoe",
                "password": "SecurePass123!"
            }
        }
    )



# -----------------------------
# 토큰 응답 스키마
# -----------------------------
class TokenOut(BaseModel):
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: Optional[str] = Field(None, description="리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: Optional[int] = Field(None, description="만료 시간 (초)")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


# -----------------------------
# 리프레시 토큰 요청 스키마
# -----------------------------
class RefreshTokenIn(BaseModel):
    refresh_token: str = Field(..., description="리프레시 토큰")

    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }


# -----------------------------
# 사용자 응답 스키마
# -----------------------------
class UserOut(BaseModel):
    id: int
    username: str
    email: str
    name: Optional[str]
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 호환
        schema_extra = {
            "example": {
                "id": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "name": "김철수",
                "is_active": True,
                "created_at": "2025-08-13T12:00:00.000Z"
            }
        }


# -----------------------------
# 비밀번호 변경 요청 스키마
# -----------------------------
class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, description="새 비밀번호")

    class Config:
        schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewSecurePass123!"
            }
        }


class LoginIn(BaseModel):
    username_or_email: str
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefreshIn(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True 


class DeactivateAccountIn(BaseModel):
    current_password: str = Field(..., min_length=8)