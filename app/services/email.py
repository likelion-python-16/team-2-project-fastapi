# app/services/email.py
import smtplib
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.models.user import User
from app.models.email_verification import EmailVerification


class EmailService:
    @staticmethod
    def _send_smtp_email(to_email: str, subject: str, html_body: str) -> None:
        """SMTP를 통해 이메일 발송 (로컬/프로덕션 모두 지원)

        - 포트 465: SMTPS(SSL)
        - 그 외: SMTP, 필요 시 STARTTLS
        - 인증 정보 미설정 시 로그인 생략 (Mailpit, Mailhog 등 로컬 테스터 호환)
        """
        if not settings.smtp_host:
            raise ValueError("SMTP_HOST가 설정되지 않았습니다")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.mail_from
        msg['To'] = to_email

        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)

        host = settings.smtp_host
        port = int(settings.smtp_port or 25)

        if port == 465:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)
            try:
                if getattr(settings, 'smtp_starttls', False):
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
            except Exception:
                # STARTTLS 실패는 무시(평문 SMTP 허용 환경일 수 있음)
                pass
        try:
            if settings.smtp_user and settings.smtp_pass:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass

    @staticmethod
    def create_verification_token(db: Session, user: User) -> str:
        """이메일 인증 토큰 생성"""
        # 기존 미사용 토큰 삭제
        db.query(EmailVerification).filter(
            EmailVerification.user_id == user.id,
            EmailVerification.used_at.is_(None)
        ).delete()
        
        # 새 토큰 생성
        token = secrets.token_urlsafe(64)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.email_token_expire_minutes)
        
        verification = EmailVerification(
            user_id=user.id,
            token=token,
            sent_to=user.email,
            expires_at=expires_at
        )
        
        db.add(verification)
        db.commit()
        
        return token

    @staticmethod
    def send_verification_email(db: Session, user: User) -> None:
        """이메일 인증 메일 발송"""
        token = EmailService.create_verification_token(db, user)
        
        verification_url = f"{settings.verification_link_base}/auth/verify-email/redirect?token={token}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>이메일 인증</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .content {{ background: #f8f9fa; padding: 30px; border-radius: 8px; }}
                .button {{ display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; text-align: center; color: #6c757d; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Team Project 이메일 인증</h1>
                </div>
                <div class="content">
                    <p>안녕하세요 {user.name}님,</p>
                    <p>Team Project에 가입해 주셔서 감사합니다!</p>
                    <p>아래 버튼을 클릭하여 이메일 인증을 완료해 주세요:</p>
                    
                    <div style="text-align: center;">
                        <a href="{verification_url}" class="button">이메일 인증하기</a>
                    </div>
                    
                    <p>버튼이 작동하지 않는 경우 아래 링크를 복사하여 브라우저에서 직접 접속하세요:</p>
                    <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 4px;">
                        {verification_url}
                    </p>
                    
                    <p><strong>주의사항:</strong></p>
                    <ul>
                        <li>이 링크는 {settings.email_token_expire_minutes}분 후 만료됩니다</li>
                        <li>본인이 요청하지 않은 경우 이 메일을 무시해 주세요</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>Team Project 팀 드림</p>
                    <p>문의사항이 있으시면 언제든 연락해 주세요.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        EmailService._send_smtp_email(
            to_email=user.email,
            subject="[Team Project] 이메일 인증을 완료해 주세요",
            html_body=html_body
        )

    @staticmethod
    def verify_email_token(db: Session, token: str) -> Optional[User]:
        """이메일 인증 토큰 검증"""
        verification = db.query(EmailVerification).filter(
            EmailVerification.token == token,
            EmailVerification.used_at.is_(None),
            EmailVerification.expires_at > datetime.utcnow()
        ).first()
        
        if not verification:
            return None
        
        # 토큰 사용 처리
        verification.used_at = datetime.utcnow()
        
        # 사용자 이메일 인증 상태 업데이트
        user = verification.user
        user.email_verified = True
        
        db.commit()
        
        return user

    @staticmethod
    def send_password_reset_email(db: Session, user: User, reset_token: str) -> None:
        """비밀번호 재설정 메일 발송"""
        reset_url = f"{settings.front_base_url}/login?reset_token={reset_token}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>비밀번호 재설정</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .content {{ background: #f8f9fa; padding: 30px; border-radius: 8px; }}
                .button {{ display: inline-block; background: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; text-align: center; color: #6c757d; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Team Project 비밀번호 재설정</h1>
                </div>
                <div class="content">
                    <p>안녕하세요 {user.name}님,</p>
                    <p>비밀번호 재설정 요청을 받았습니다.</p>
                    <p>아래 버튼을 클릭하여 새로운 비밀번호를 설정하세요:</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_url}" class="button">비밀번호 재설정</a>
                    </div>
                    
                    <p>버튼이 작동하지 않는 경우 아래 링크를 복사하여 브라우저에서 직접 접속하세요:</p>
                    <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 4px;">
                        {reset_url}
                    </p>
                    
                    <p><strong>주의사항:</strong></p>
                    <ul>
                        <li>이 링크는 30분 후 만료됩니다</li>
                        <li>본인이 요청하지 않은 경우 이 메일을 무시해 주세요</li>
                        <li>보안을 위해 다른 사람과 이 링크를 공유하지 마세요</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>Team Project 팀 드림</p>
                    <p>문의사항이 있으시면 언제든 연락해 주세요.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        EmailService._send_smtp_email(
            to_email=user.email,
            subject="[Team Project] 비밀번호 재설정 요청",
            html_body=html_body
        )
