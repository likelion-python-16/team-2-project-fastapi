# app/schemas/auth.py (최종)
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re

# ---------------------------
# 요청 스키마
# ---------------------------
class SignUpIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    email: EmailStr = Field(..., description="이메일 주소(최대 120자)")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)")

    # 필수: 010-11자리
    phone: str = Field(..., description="전화번호(필수, 010으로 시작, 총 11자리)")

    # 필수: 13자리 + YYMMDD + 7번째(1~8)
    identification_number: str = Field(..., description="식별번호 13자리 (필수)")

    # 선택 입력
    name: Optional[str] = Field(None, max_length=100, description="실명 (선택)")
    gender: Optional[str] = Field(None, description="성별: male/female/other (미입력시 other)")
    region_living: Optional[str] = Field(None, max_length=50, description="생활 지역 (선택)")
    region_active: Optional[str] = Field(None, max_length=50, description="활동 지역 (선택)")
    profile_image: Optional[str] = Field(None, max_length=255, description="프로필 이미지 URL (선택)")
    introduction: Optional[str] = Field(None, description="소개 (선택, 미입력시 '')")

    @validator('username')
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]+$', v or ''):
            raise ValueError('사용자명은 영문, 숫자, 언더스코어(_)만 사용 가능합니다')
        if not v[0].isalpha():
            raise ValueError('사용자명은 영문으로 시작해야 합니다')
        return v.lower()

    @validator('email')
    def validate_email_len(cls, v: EmailStr) -> EmailStr:
        if len(str(v)) > 120:
            raise ValueError('이메일은 120자 이하여야 합니다')
        return v

    @validator('phone', pre=True)
    def normalize_phone_010(cls, v: str) -> str:
        s = re.sub(r'\D+', '', str(v or ''))
        if not re.fullmatch(r'010\d{8}', s):
            raise ValueError('전화번호는 010으로 시작하는 11자리여야 합니다')
        return f'010-{s[3:7]}-{s[7:11]}'

    @validator('name', pre=True)
    def normalize_name(cls, v: Optional[str]) -> str:
        if v is None:
            return ''
        v = v.strip()
        if not v:
            return ''
        if len(v) < 2:
            raise ValueError('실명은 2자 이상이어야 합니다')
        return v

    @validator('identification_number', pre=True)
    def validate_identification_number(cls, v: str) -> str:
        n = re.sub(r'\D+', '', str(v or ''))
        if not re.fullmatch(r'\d{13}', n):
            raise ValueError('식별번호는 13자리 숫자여야 합니다')
        if n[2] not in ('0','1'):
            raise ValueError('월의 십의 자리는 0 또는 1이어야 합니다')
        if n[4] not in ('0','1','2','3'):
            raise ValueError('일의 십의 자리는 0-3이어야 합니다')
        m = int(n[2:4]); d = int(n[4:6])
        if not (1 <= m <= 12):
            raise ValueError('월은 01-12여야 합니다')
        if not (1 <= d <= 31):
            raise ValueError('일은 01-31이어야 합니다')
        if n[6] not in '12345678':
            raise ValueError('7번째 자리는 1-8이어야 합니다')
        return n

    @validator('gender', pre=True)
    def normalize_gender(cls, v: Optional[str]) -> str:
        if not v:
            return 'other'
        v = str(v).strip().lower()
        return {'m':'male','male':'male','f':'female','female':'female','u':'other','other':'other'}.get(v, 'other')

    @validator('region_living', 'region_active', 'profile_image', 'introduction', pre=True)
    def normalize_text_defaults(cls, v: Optional[str]) -> str:
        return '' if v is None else str(v).strip()

    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "SecurePass123!",
                "name": "김철수",
                "phone": "010-1234-5678",
                "identification_number": "9012011234567",
                "gender": "other",
                "region_living": "",
                "region_active": "",
                "profile_image": "",
                "introduction": ""
            }
        }


class LoginIn(BaseModel):
    login: str = Field(..., description="사용자명 또는 이메일")
    password: str = Field(..., description="비밀번호")

    @validator('login')
    def validate_login(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자명 또는 이메일을 입력해주세요')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {"login": "johndoe", "password": "SecurePass123!"}
        }

# ---------------------------
# 응답 스키마
# ---------------------------
class TokenOut(BaseModel):
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: Optional[int] = Field(None, description="만료 시간(초)")

class RefreshTokenIn(BaseModel):
    refresh_token: str = Field(..., description="리프레시 토큰")

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    name: Optional[str] = ""
    is_active: Optional[bool] = True
    gender: Optional[str] = "other"
    region_living: Optional[str] = ""
    region_active: Optional[str] = ""
    profile_image: Optional[str] = ""
    introduction: Optional[str] = ""
    manner_score: Optional[float] = 0
    total_points: Optional[int] = 0
    penalty_total: Optional[int] = 0
    is_admin: Optional[bool] = False
    email_verified: Optional[bool] = False
    token_version: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, description="새 비밀번호")
