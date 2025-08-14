from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional
import re
from datetime import datetime

# -----------------------------
# 회원가입 요청 스키마
# -----------------------------
class SignUpIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)")
    name: Optional[str] = Field(None, max_length=100, description="실명 (선택사항)")
    identification_number: Optional[str] = Field(None, description="식별번호 (선택사항)")

    @validator('username')
    def validate_username(cls, v):
        if not v:
            raise ValueError('사용자명은 필수입니다')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('사용자명은 영문, 숫자, 언더스코어(_)만 사용 가능합니다')
        if not v[0].isalpha():
            raise ValueError('사용자명은 영문으로 시작해야 합니다')
        return v.lower()

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 2:
                raise ValueError('실명은 2자 이상이어야 합니다')
        return v

    @validator('identification_number')
    def validate_identification_number(cls, v):
        if v is not None:
            v = v.replace('-', '')
            if not re.match(r'^\d{13}$', v):
                raise ValueError('식별번호는 13자리 숫자여야 합니다')
            if v[6] not in ['1', '2', '3', '4']:
                raise ValueError('올바르지 않은 식별번호 형식입니다')
        return v

    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "SecurePass123!",
                "name": "김철수",
                "identification_number": "9012011234567"
            }
        }


# -----------------------------
# 로그인 요청 스키마
# -----------------------------
class LoginIn(BaseModel):
    login: str = Field(..., description="사용자명 또는 이메일")
    password: str = Field(..., description="비밀번호")

    @validator('login')
    def validate_login(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자명 또는 이메일을 입력해주세요')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "login": "johndoe",
                "password": "SecurePass123!"
            }
        }


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
