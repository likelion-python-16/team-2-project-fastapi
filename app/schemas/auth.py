from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional
import re

class SignUpIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)")
    name: Optional[str] = Field(None, max_length=100, description="실명 (선택사항)")
    identification_number: Optional[str] = Field(None, description="식별번호 (선택사항)")
    
    @validator('username')
    def validate_username(cls, v):
        """사용자명 검증"""
        if not v:
            raise ValueError('사용자명은 필수입니다')
        
        # 영문, 숫자, 언더스코어만 허용
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('사용자명은 영문, 숫자, 언더스코어(_)만 사용 가능합니다')
        
        # 첫 글자는 영문이어야 함
        if not v[0].isalpha():
            raise ValueError('사용자명은 영문으로 시작해야 합니다')
        
        return v.lower()  # 소문자로 변환
    
    @validator('name')
    def validate_name(cls, v):
        """실명 검증"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 2:
                raise ValueError('실명은 2자 이상이어야 합니다')
        return v
    
    @validator('identification_number')
    def validate_identification_number(cls, v):
        """식별번호 검증 (주민등록번호, 외국인등록번호 등)"""
        if v is not None:
            # 하이픈 제거
            v = v.replace('-', '')
            
            # 13자리 숫자 확인
            if not re.match(r'^\d{13}$', v):
                raise ValueError('식별번호는 13자리 숫자여야 합니다')
            
            # 간단한 주민등록번호 검증 (더 상세한 검증 가능)
            birth_date = v[:6]
            gender_code = v[6]
            
            if gender_code not in ['1', '2', '3', '4']:
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

class LoginIn(BaseModel):
    login: str = Field(..., description="사용자명 또는 이메일")
    password: str = Field(..., description="비밀번호")
    
    @validator('login')
    def validate_login(cls, v):
        """로그인 필드 검증"""
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자명 또는 이메일을 입력해주세요')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "login": "johndoe",  # 또는 "john@example.com"
                "password": "SecurePass123!"
            }
        }

class TokenOut(BaseModel):
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
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

class RefreshTokenIn(BaseModel):
    refresh_token: str = Field(..., description="리프레시 토큰")
    
    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }

from datetime import datetime

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    name: Optional[str]
    is_active: bool
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Pydantic v2
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