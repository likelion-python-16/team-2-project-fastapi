from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# 회원가입 요청 스키마
class SignUpIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, description="사용자명")
    email: EmailStr
    password: str = Field(..., min_length=8, description="비밀번호")
    name: Optional[str] = Field(None, max_length=50, description="이름")
    identification_number: Optional[str] = Field(None, description="식별 번호 (선택)")

    class Config:
        orm_mode = True


# 로그인 요청 스키마
class LoginIn(BaseModel):
    login: str = Field(..., description="아이디 또는 이메일")
    password: str = Field(..., min_length=8, description="비밀번호")


# 토큰 응답 스키마
class TokenOut(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"


# 리프레시 토큰 요청 스키마
class RefreshTokenIn(BaseModel):
    refresh_token: str
