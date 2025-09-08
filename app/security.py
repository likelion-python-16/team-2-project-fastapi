# app/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, TYPE_CHECKING
from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.utils.logging import logger
from app.core.database import get_db
import hmac, hashlib, re

# 타입 힌트 전용 (런타임 임포트 금지)
if TYPE_CHECKING:
    from app.models.user import User  # noqa: F401

# -------------------------------
# 기본 설정 & 유틸
# -------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes

# 로그인 토큰 발급 엔드포인트 경로에 맞추세요(문서용)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# 선택적 인증이 필요한 엔드포인트용(헤더 없으면 None)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    권장: data에는 최소한 {"sub": str(user.id)} 형태로 user_id를 넣어주세요.
    추가 메타로 {"username": user.username, "ver": user.token_version}도 유용합니다.
    """
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    try:
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"JWT 토큰 생성 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="토큰 생성에 실패했습니다")

def verify_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            logger.warning("잘못된 토큰 타입")
            return None
        # ExpiredSignatureError는 decode에서 이미 처리됨
        return payload
    except ExpiredSignatureError:
        logger.info("만료된 JWT 토큰")
        return None
    except JWTError as e:
        logger.warning(f"유효하지 않은 JWT 토큰: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT 토큰 검증 오류: {e}")
        return None

def create_refresh_token(data: dict) -> str:
    if not data:
        raise ValueError("토큰 데이터가 비어있습니다")
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=7)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    try:
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"리프레시 토큰 생성 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="리프레시 토큰 생성에 실패했습니다")

def verify_refresh_token(token: str) -> Optional[dict]:
    if not token:
        return None
    # 블랙리스트 체크 추가
    if is_refresh_token_revoked(token):
        logger.info("취소된 리프레시 토큰")
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
    except JWTError as e:
        logger.warning(f"유효하지 않은 리프레시 토큰: {e}")
        return None
    except Exception as e:
        logger.error(f"리프레시 토큰 검증 오류: {e}")
        return None

def get_fernet_key() -> bytes:
    try:
        return settings.fernet_key.encode()
    except Exception as e:
        logger.error(f"Fernet 키 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="암호화 키 설정 오류")

def encrypt_str(plain_str: str) -> str:
    if not plain_str:
        raise ValueError("암호화할 문자열이 비어있습니다")
    try:
        fernet = Fernet(get_fernet_key())
        return fernet.encrypt(plain_str.encode()).decode()
    except Exception as e:
        logger.error(f"암호화 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="데이터 암호화에 실패했습니다")

def decrypt_str(encrypted_str: str) -> str:
    if not encrypted_str:
        raise ValueError("복호화할 문자열이 비어있습니다")
    try:
        fernet = Fernet(get_fernet_key())
        return fernet.decrypt(encrypted_str.encode()).decode()
    except Exception as e:
        logger.error(f"복호화 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="데이터 복호화에 실패했습니다")

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

ID_FINGERPRINT_SECRET = settings.id_fingerprint_secret

def normalize_phone(phone: str) -> str:
    if not phone:
        return phone
    return re.sub(r"\D+", "", phone)

def id_fingerprint(plain_id: str) -> Optional[str]:
    if not plain_id:
        return None
    normalized = re.sub(r"\D+", "", plain_id)
    mac = hmac.new(
        ID_FINGERPRINT_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return mac

# (테스트용) 인메모리 리프레시 토큰 블랙리스트
REVOKED_REFRESH_TOKENS = set()

def revoke_refresh_token(token: str) -> None:
    REVOKED_REFRESH_TOKENS.add(token)

def is_refresh_token_revoked(token: str) -> bool:
    return token in REVOKED_REFRESH_TOKENS

# -------------------------------
# 의존성: 현재 사용자 가져오기 (지연 임포트로 순환 방지)
# -------------------------------
def _extract_user_identifier(payload: dict) -> Optional[Union[int, str]]:
    """일반적으로 'sub'에서 사용자 식별자를 꺼냄 (id 권장)"""
    if not payload:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return sub  # username/email 등일 수 있음

def _matches_token_version(user, payload: dict) -> bool:
    """토큰의 ver(토큰 버전)과 DB의 token_version이 다르면 False"""
    if not hasattr(user, "token_version"):
        return True
    # Accept both 'tv' (preferred) and 'ver' (legacy)
    token_ver = payload.get("tv", payload.get("ver"))
    if token_ver is None:
        return True  # ver 미포함 토큰은 허용(레거시)
    try:
        return int(token_ver) == int(getattr(user, "token_version", 0))
    except (TypeError, ValueError):
        return False

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Authorization: Bearer <token> 기반 인증 사용자 반환.
    여기서만 User 클래스를 지연 임포트하여 순환 임포트를 피합니다.
    """
    from app.models.user import User  # 지연 임포트 (중요)

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 자격 증명이 유효하지 않습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if not payload:
        raise credentials_exc

    user_ident = _extract_user_identifier(payload)
    if user_ident is None:
        logger.warning("토큰에 사용자 식별자(sub)가 없습니다")
        raise credentials_exc

    if isinstance(user_ident, int):
        user = db.query(User).filter(User.id == user_ident).first()
    else:
        # 레거시: sub가 username/email 로 들어온 경우도 처리
        if hasattr(User, "username"):
            user = db.query(User).filter(User.username == str(user_ident)).first()
        elif hasattr(User, "email"):
            user = db.query(User).filter(User.email == str(user_ident)).first()
        else:
            user = None

    if not user:
        logger.info(f"사용자를 찾을 수 없음: {user_ident}")
        raise credentials_exc

    if hasattr(user, "is_active") and not getattr(user, "is_active"):
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다")

    # 토큰 버전 검증(선택적)
    if not _matches_token_version(user, payload):
        raise HTTPException(status_code=401, detail="토큰 버전 불일치(만료)")

    return user

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
):
    """토큰이 유효하면 User, 아니면 None 반환 (공개 엔드포인트에서 선택적 사용)"""
    try:
        if not token:
            return None
        payload = verify_token(token)
        if not payload:
            return None
        user_ident = _extract_user_identifier(payload)
        if user_ident is None:
            return None

        from app.models.user import User  # 지연 임포트

        if isinstance(user_ident, int):
            user = db.query(User).filter(User.id == user_ident).first()
        else:
            if hasattr(User, "username"):
                user = db.query(User).filter(User.username == str(user_ident)).first()
            elif hasattr(User, "email"):
                user = db.query(User).filter(User.email == str(user_ident)).first()
            else:
                user = None

        if not user:
            return None
        if hasattr(user, "is_active") and not getattr(user, "is_active"):
            return None
        if not _matches_token_version(user, payload):
            return None
        return user
    except Exception:
        return None
