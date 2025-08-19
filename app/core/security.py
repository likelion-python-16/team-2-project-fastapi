"""
보안 유틸:
- 비밀번호 해시/검증(bcrypt)
- 필드 암호화(AES-GCM): 주민번호/휴대폰 등
- JWT 발급/검증(access/refresh)

ENV (또는 settings):
  SECRET_KEY      : JWT 서명 키 (필수)
  FIELD_AES_KEY   : AES 키(hex, 16/24/32바이트)
  ALGORITHM       : JWT 알고리즘 (기본 HS256)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, secrets

from jose import jwt, JWTError

# settings가 있으면 우선 사용, 없으면 env fallback
try:
    from app.core.config import settings  # 선택적
except Exception:
    settings = None  # 없으면 env만 사용

# ------------------------------
# 비밀번호 해시/검증 (bcrypt)
# ------------------------------
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)

# ------------------------------
# 필드 암호화(AES-GCM)
# ------------------------------
def _get_field_key() -> bytes:
    key_hex = getattr(settings, "FIELD_AES_KEY", None) if settings else None
    key_hex = key_hex or os.getenv("FIELD_AES_KEY")
    if not key_hex:
        raise RuntimeError("FIELD_AES_KEY not set (hex)")
    key = bytes.fromhex(key_hex)
    if len(key) not in (16, 24, 32):
        raise RuntimeError("FIELD_AES_KEY must be 16/24/32 bytes")
    return key

def encrypt_field(plaintext: str) -> bytes:
    key = _get_field_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct

def decrypt_field(cipher: bytes) -> str:
    key = _get_field_key()
    aesgcm = AESGCM(key)
    nonce, ct = cipher[:12], cipher[12:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")

def encrypt_str(plaintext: str) -> str:
    return encrypt_field(plaintext).hex()

def decrypt_str(cipher_hex: str) -> str:
    return decrypt_field(bytes.fromhex(cipher_hex))

def mask_last4(s: str) -> str:
    if not s or len(s) < 4:
        return "***"
    return "***-****-" + s[-4:]

# ------------------------------
# JWT
# ------------------------------
ALGORITHM = (getattr(settings, "ALGORITHM", None) if settings else None) or os.getenv("ALGORITHM", "HS256")

def _get_secret() -> str:
    secret = getattr(settings, "SECRET_KEY", None) if settings else None
    secret = secret or os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY not set")
    return secret

def _jwt_encode(data: Dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode.update({"iat": now, "exp": now + expires_delta})
    return jwt.encode(to_encode, _get_secret(), algorithm=ALGORITHM)

def _jwt_decode(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])

def create_access_token(*, sub: str, tv: int, minutes: int = 120) -> str:
    return _jwt_encode({"sub": sub, "type": "access", "tv": tv}, timedelta(minutes=minutes))

def create_refresh_token(*, sub: str, tv: int, days: int = 7) -> str:
    return _jwt_encode({"sub": sub, "type": "refresh", "tv": tv}, timedelta(days=days))

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return _jwt_decode(token)
    except JWTError as e:
        raise ValueError("Invalid token") from e

