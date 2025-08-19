# app/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from fastapi import HTTPException, status
from cryptography.fernet import Fernet

# ⚠️ settings 경로는 프로젝트에 맞추세요.
# 예: from app.core.config import settings  (당신 프로젝트에 이미 있음)
from app.core.config import settings
from app.utils.logging import logger

# --------------------------
# 비밀번호 해싱
# --------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("비밀번호가 비어있습니다")
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"비밀번호 검증 오류: {e}")
        return False

# --------------------------
# JWT 설정
# --------------------------
SECRET_KEY = settings.resolved_secret_key       # ← 통합된 시크릿
ALGORITHM = settings.resolved_algorithm         # ← 통합된 알고리즘
ACCESS_TOKEN_EXPIRE_MINUTES = settings.resolved_access_token_expire_minutes

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode = {
        **data,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    try:
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"JWT 토큰 생성 오류: {e}")
        raise HTTPException(status_code=500, detail="토큰 생성에 실패했습니다")

def verify_access_token(token: str) -> Optional[dict]:
    """
    Access JWT 검증 후 payload 반환.
    실패 시 None 반환.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            logger.warning("잘못된 토큰 타입(access 아님)")
            return None
        # jose가 exp를 자동 검증하지만, 명시적으로 한 번 더 확인(선택)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            logger.info("만료된 토큰")
            return None
        return payload
    except ExpiredSignatureError:
        logger.info("만료된 JWT 토큰")
        return None
    except JWTError:
        logger.warning("유효하지 않은 JWT 토큰")
        return None
    except Exception as e:
        logger.error(f"JWT 토큰 검증 오류: {e}")
        return None

def create_refresh_token(data: dict) -> str:
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")

    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=7)
    to_encode = {
        **data,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    try:
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"리프레시 토큰 생성 오류: {e}")
        raise HTTPException(status_code=500, detail="리프레시 토큰 생성에 실패했습니다")

def verify_refresh_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            logger.warning("잘못된 리프레시 토큰 타입")
            return None
        return payload
    except ExpiredSignatureError:
        logger.info("만료된 리프레시 토큰")
        return None
    except JWTError:
        logger.warning("유효하지 않은 리프레시 토큰")
        return None
    except Exception as e:
        logger.error(f"리프레시 토큰 검증 오류: {e}")
        return None

# --------------------------
# 식별번호 암/복호화 (Fernet)
# --------------------------
def get_fernet_key() -> bytes:
    try:
        # settings.fernet_key 가 URL-safe base64 32바이트여야 함
        return (settings.field_aes_key or settings.fernet_key).encode()
    except Exception as e:
        logger.error(f"Fernet 키 오류: {e}")
        raise HTTPException(status_code=500, detail="암호화 키 설정 오류")

def encrypt_str(plain_str: str) -> str:
    if not plain_str:
        raise ValueError("암호화할 문자열이 비어있습니다")
    try:
        f = Fernet(get_fernet_key())
        return f.encrypt(plain_str.encode()).decode()
    except Exception as e:
        logger.error(f"암호화 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터 암호화에 실패했습니다")

def decrypt_str(encrypted_str: str) -> str:
    if not encrypted_str:
        raise ValueError("복호화할 문자열이 비어있습니다")
    try:
        f = Fernet(get_fernet_key())
        return f.decrypt(encrypted_str.encode()).decode()
    except Exception as e:
        logger.error(f"복호화 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터 복호화에 실패했습니다")

def validate_password_strength(password: str) -> bool:
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    return has_upper and has_lower and has_digit and has_special

def get_password_requirements() -> dict:
    return {
        "min_length": 8,
        "requires_uppercase": True,
        "requires_lowercase": True,
        "requires_digit": True,
        "requires_special_char": True,
        "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?",
        "message": "8자 이상, 대소문자, 숫자, 특수문자를 포함해야 합니다",
    }
