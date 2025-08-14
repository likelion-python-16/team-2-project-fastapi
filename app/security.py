# app/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from cryptography.fernet import Fernet
from app.core.config import settings
from app.utils.logging import logger

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 설정 (config.py에서 가져오기)
SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes

def hash_password(password: str) -> str:
    """비밀번호 해싱"""
    if not password:
        raise ValueError("비밀번호가 비어있습니다")
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"비밀번호 검증 오류: {e}")
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 토큰 생성"""
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # 발급 시간 추가
        "type": "access"  # 토큰 타입 추가
    })
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"JWT 토큰 생성 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 생성에 실패했습니다"
        )

def verify_token(token: str) -> Optional[dict]:
    """JWT 토큰 검증"""
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 토큰 타입 검증
        if payload.get("type") != "access":
            logger.warning("잘못된 토큰 타입")
            return None
        
        # 만료 시간 체크 (jose에서 자동으로 체크하지만 명시적으로 추가)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            logger.info("만료된 토큰")
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("만료된 JWT 토큰")
        return None
    except jwt.InvalidTokenError:
        logger.warning("유효하지 않은 JWT 토큰")
        return None
    except Exception as e:
        logger.error(f"JWT 토큰 검증 오류: {e}")
        return None

def create_refresh_token(data: dict) -> str:
    """리프레시 토큰 생성 (7일 만료)"""
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")
    
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"  # 리프레시 토큰 타입
    })
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"리프레시 토큰 생성 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리프레시 토큰 생성에 실패했습니다"
        )

def verify_refresh_token(token: str) -> Optional[dict]:
    """리프레시 토큰 검증"""
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 토큰 타입 검증
        if payload.get("type") != "refresh":
            logger.warning("잘못된 리프레시 토큰 타입")
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("만료된 리프레시 토큰")
        return None
    except jwt.InvalidTokenError:
        logger.warning("유효하지 않은 리프레시 토큰")
        return None
    except Exception as e:
        logger.error(f"리프레시 토큰 검증 오류: {e}")
        return None

# 암호화/복호화 (식별번호용) - Fernet 사용
def get_fernet_key() -> bytes:
    """Fernet 키 가져오기"""
    try:
        return settings.fernet_key.encode()
    except Exception as e:
        logger.error(f"Fernet 키 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="암호화 키 설정 오류"
        )

def encrypt_str(plain_str: str) -> str:
    """문자열 암호화 (Fernet 사용)"""
    if not plain_str:
        raise ValueError("암호화할 문자열이 비어있습니다")
    
    try:
        fernet = Fernet(get_fernet_key())
        encrypted_bytes = fernet.encrypt(plain_str.encode())
        return encrypted_bytes.decode()
    except Exception as e:
        logger.error(f"암호화 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터 암호화에 실패했습니다"
        )

def decrypt_str(encrypted_str: str) -> str:
    """문자열 복호화"""
    if not encrypted_str:
        raise ValueError("복호화할 문자열이 비어있습니다")
    
    try:
        fernet = Fernet(get_fernet_key())
        decrypted_bytes = fernet.decrypt(encrypted_str.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        logger.error(f"복호화 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터 복호화에 실패했습니다"
        )

def validate_password_strength(password: str) -> bool:
    """비밀번호 강도 검증"""
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    return has_upper and has_lower and has_digit and has_special

def get_password_requirements() -> dict:
    """비밀번호 요구사항 반환"""
    return {
        "min_length": 8,
        "requires_uppercase": True,
        "requires_lowercase": True,
        "requires_digit": True,
        "requires_special_char": True,
        "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?",
        "message": "8자 이상, 대소문자, 숫자, 특수문자를 포함해야 합니다"
    }