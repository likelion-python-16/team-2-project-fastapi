# app/services/auth_service.py
from datetime import timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.auth import SignUpIn, LoginIn, TokenOut, UserOut, PasswordChangeIn
from app.security import (
    hash_password, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    encrypt_str,
    id_fingerprint,
    normalize_phone
)
from app.utils.logging import logger


class AuthService:
    """인증 관련 비즈니스 로직을 담당하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_data: SignUpIn) -> Tuple[User, TokenOut]:
        """
        사용자 회원가입
        Returns: (생성된 사용자, 토큰 정보)
        """
        # 1. 중복 검사
        self._check_user_exists(user_data.username, user_data.email)
        
        # 2. 사용자 생성
        db_user = self._create_user(user_data)
        
        # 3. 토큰 생성
        tokens = self._create_user_tokens(db_user)
        
        logger.info(f"새 사용자 등록: {db_user.username} (ID: {db_user.id})")
        return db_user, tokens

    def authenticate_user(self, login_data: LoginIn) -> Tuple[User, TokenOut]:
        """
        사용자 로그인 인증
        Returns: (인증된 사용자, 토큰 정보)
        """
        # 1. 사용자 찾기 (username 또는 email로)
        user = self._find_user_by_login(login_data.login)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다"
            )
        
        # 2. 비밀번호 확인
        if not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다"
            )
        
        # 3. 계정 활성화 확인
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정입니다"
            )
        
        # 4. 토큰 생성
        tokens = self._create_user_tokens(user)
        
        logger.info(f"사용자 로그인: {user.username} (ID: {user.id})")
        return user, tokens

    def refresh_access_token(self, refresh_token: str) -> TokenOut:
        """리프레시 토큰으로 새 액세스 토큰 발급"""
        # 1. 리프레시 토큰 검증
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 리프레시 토큰입니다"
            )
        
        # 2. 사용자 확인
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다"
            )
        
        user = self.db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없거나 비활성화된 계정입니다"
            )
        
        # 3. 토큰 버전 확인
        if payload.get("ver") != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 버전이 만료되었습니다"
            )
        
        # 4. 새 토큰 발급
        tokens = self._create_user_tokens(user)
        
        # 5. 기존 리프레시 토큰 무효화
        revoke_refresh_token(refresh_token)
        
        logger.info(f"토큰 갱신: {user.username} (ID: {user.id})")
        return tokens

    def logout_user(self, refresh_token: str) -> None:
        """사용자 로그아웃 (리프레시 토큰 무효화)"""
        revoke_refresh_token(refresh_token)
        logger.info("사용자 로그아웃 완료")

    def change_password(self, user: User, password_data: PasswordChangeIn) -> bool:
        """비밀번호 변경"""
        # 1. 현재 비밀번호 확인
        if not verify_password(password_data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호가 올바르지 않습니다"
            )
        
        # 2. 새 비밀번호 해시화
        new_password_hash = hash_password(password_data.new_password)
        
        # 3. 비밀번호 업데이트
        user.password_hash = new_password_hash
        user.token_version += 1  # 기존 토큰들 무효화
        
        self.db.commit()
        logger.info(f"비밀번호 변경: {user.username} (ID: {user.id})")
        return True

    def deactivate_user(self, user: User) -> bool:
        """사용자 계정 비활성화"""
        user.is_active = False
        user.token_version += 1  # 기존 토큰들 무효화
        
        self.db.commit()
        logger.info(f"계정 비활성화: {user.username} (ID: {user.id})")
        return True

    def get_user_profile(self, user: User) -> UserOut:
        """사용자 프로필 조회"""
        return UserOut.model_validate(user)

    # ==================== Private Methods ====================
    
    def _check_user_exists(self, username: str, email: str) -> None:
        """사용자 중복 검사"""
        existing_user = self.db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 사용 중인 사용자명입니다"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 사용 중인 이메일입니다"
                )

    def _create_user(self, user_data: SignUpIn) -> User:
        """사용자 데이터베이스 레코드 생성"""
        # 비밀번호 해시화
        password_hash = hash_password(user_data.password)
        
        # 전화번호 암호화 (있을 경우)
        phone_encrypted = None
        phone_fingerprint = None
        if user_data.phone:
            normalized_phone = normalize_phone(user_data.phone)
            phone_encrypted = encrypt_str(normalized_phone)
            phone_fingerprint = id_fingerprint(normalized_phone)
        
        # 주민번호 처리 (있을 경우)
        id_encrypted = None
        id_fingerprint_value = None
        if user_data.identification_number:
            id_encrypted = encrypt_str(user_data.identification_number)
            id_fingerprint_value = id_fingerprint(user_data.identification_number)

        # 사용자 생성
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_hash,
            name=user_data.name or "",
            gender=user_data.gender or "other",
            region_living=user_data.region_living or "",
            region_active=user_data.region_active or "",
            profile_image=user_data.profile_image or "",
            introduction=user_data.introduction or "",
            phone_encrypted=phone_encrypted,
            phone_fingerprint=phone_fingerprint,
            identification_number_encrypted=id_encrypted,
            identification_number_fingerprint=id_fingerprint_value,
            is_active=True,
            token_version=0
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        return db_user

    def _find_user_by_login(self, login: str) -> Optional[User]:
        """로그인 ID로 사용자 찾기 (username 또는 email)"""
        return self.db.query(User).filter(
            (User.username == login) | (User.email == login)
        ).first()

    def _create_user_tokens(self, user: User) -> TokenOut:
        """사용자 토큰 생성 (액세스 + 리프레시)"""
        # 토큰에 포함할 데이터
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "ver": user.token_version
        }
        
        # 액세스 토큰
        access_token = create_access_token(token_data)
        
        # 리프레시 토큰
        refresh_token = create_refresh_token(token_data)
        
        return TokenOut(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=1800  # 30분
        )


# ==================== Service Factory ====================

def get_auth_service(db: Session) -> AuthService:
    """AuthService 인스턴스 생성 (의존성 주입용)"""
    return AuthService(db)