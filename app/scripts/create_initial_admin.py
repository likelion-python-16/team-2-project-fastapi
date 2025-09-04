#!/usr/bin/env python3
"""
초기 관리자 생성 스크립트
환경변수 기반으로 첫 번째 슈퍼관리자를 생성합니다.
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.user import User
from app.security import hash_password


def create_initial_admin():
    """환경변수 설정 기반으로 초기 관리자 생성"""
    
    # 필수 환경변수 체크
    if not all([
        settings.initial_admin_username,
        settings.initial_admin_email,
        settings.initial_admin_password
    ]):
        print("❌ 초기 관리자 환경변수가 설정되지 않았습니다.")
        print("다음 환경변수를 설정해주세요:")
        print("- INITIAL_ADMIN_USERNAME")
        print("- INITIAL_ADMIN_EMAIL") 
        print("- INITIAL_ADMIN_PASSWORD")
        print("- INITIAL_ADMIN_NAME (선택, 기본값: System Admin)")
        return False

    db: Session = SessionLocal()
    try:
        # 기존 슈퍼관리자가 있는지 확인
        existing_superadmin = db.query(User).filter(User.is_superadmin == True).first()
        if existing_superadmin:
            print(f"⚠️  이미 슈퍼관리자가 존재합니다: {existing_superadmin.username}")
            return True

        # 동일한 사용자명이나 이메일이 존재하는지 확인
        existing_user = db.query(User).filter(
            (User.username == settings.initial_admin_username.lower()) |
            (User.email == settings.initial_admin_email.lower())
        ).first()
        
        if existing_user:
            print(f"⚠️  동일한 사용자명 또는 이메일이 이미 존재합니다.")
            print(f"기존 사용자 '{existing_user.username}'를 슈퍼관리자로 승급시킵니다.")
            existing_user.is_admin = True
            existing_user.is_superadmin = True
            db.commit()
            print(f"✅ '{existing_user.username}' 사용자가 슈퍼관리자로 승급되었습니다.")
            return True

        # 새로운 슈퍼관리자 생성
        admin_user = User(
            username=settings.initial_admin_username.lower(),
            email=settings.initial_admin_email.lower(),
            password_hash=hash_password(settings.initial_admin_password),
            name=settings.initial_admin_name,
            phone=None,  # 선택사항
            region_living="서울",
            region_active="서울", 
            profile_image="",
            is_admin=True,
            is_superadmin=True,
            email_verified=True,
            is_active=True,
            introduction="시스템 초기 관리자",
            gender="other"
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print(f"✅ 초기 슈퍼관리자가 생성되었습니다!")
        print(f"   - 사용자명: {admin_user.username}")
        print(f"   - 이메일: {admin_user.email}")
        print(f"   - 이름: {admin_user.name}")
        print(f"   - ID: {admin_user.id}")
        
        return True

    except Exception as e:
        print(f"❌ 초기 관리자 생성 중 오류가 발생했습니다: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 초기 관리자 생성 스크립트 실행")
    success = create_initial_admin()
    
    if success:
        print("🎉 초기 관리자 설정이 완료되었습니다.")
    else:
        print("💥 초기 관리자 생성에 실패했습니다.")
        sys.exit(1)