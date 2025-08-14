from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, secrets, binascii
from datetime import datetime, timedelta
from jose import jwt, JWTError  # pip install python-jose

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)

def _get_key() -> bytes:
    key_hex = os.getenv("FIELD_AES_KEY")
    if not key_hex:
        raise RuntimeError("FIELD_AES_KEY not set")
    try:
        key = bytes.fromhex(key_hex)
    except binascii.Error:
        raise RuntimeError("FIELD_AES_KEY must be hex")
    if len(key) not in (16, 24, 32):
        raise RuntimeError("FIELD_AES_KEY must be 16/24/32 bytes")
    return key

def encrypt_field(plaintext: str) -> bytes:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ct

def decrypt_field(cipher: bytes) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce, ct = cipher[:12], cipher[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()

def mask_last4(s: str) -> str:
    if not s or len(s) < 4: return "***"
    return "***-****-" + s[-4:]
def encrypt_str(plaintext: str) -> str:
    """평문 -> (nonce|ciphertext) bytes -> hex str"""
    return encrypt_field(plaintext).hex()

def decrypt_str(cipher_hex: str) -> str:
    """hex str -> bytes -> 평문"""
    return decrypt_field(bytes.fromhex(cipher_hex))

def _get_secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY not set")
    return secret

def _get_alg() -> str:
    return os.getenv("ALGORITHM", "HS256")

def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _get_secret(), algorithm=_get_alg())

def decode_access_token(token: str):
    """
    유효하면 payload(dict) 반환, 실패하면 None.
    payload 안에 보통 'sub'로 user_id를 담아둔다.
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_get_alg()])
        return payload
    except JWTError:
        return None