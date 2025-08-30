# app/services/mailer.py
import smtplib, ssl
from email.message import EmailMessage
from app.core.config import settings

def build_verify_url(token: str) -> str:
    """
    인증 버튼/텍스트 링크에 쓰이는 최종 URL.
    반드시 백엔드(8001)로 들어오도록 verification_link_base 사용.
    """
    return f"{settings.verification_link_base}/auth/verify-email/redirect?token={token}"

def build_password_reset_url(token: str) -> str:
    """
    비밀번호 재설정 링크: 백엔드 리디렉트 엔드포인트로 유도하여
    배포 환경(도메인/포트)에서도 자동으로 프론트 URL을 계산하도록 합니다.
    """
    base = settings.verification_link_base.rstrip('/') or 'http://localhost:8001/api/v1'
    return f"{base}/auth/password-reset/redirect?token={token}"

def build_password_reset_email(token: str, username: str) -> tuple[str, str]:
    url = build_password_reset_url(token)
    html = f"""
    <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"font-family:Arial, Helvetica, sans-serif; background:#ffffff;\">
      <tr>
        <td style=\"padding:24px; font-size:14px; line-height:1.6; color:#111827;\">
          <h3 style=\"margin:0 0 12px 0; font-size:18px; color:#111827;\">비밀번호 재설정</h3>
          <p style=\"margin:0 0 16px 0;\">아래 버튼을 눌러 <b>{username}</b> 계정의 비밀번호를 재설정해 주세요.</p>
          <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" style=\"margin:0 0 16px 0; border-collapse:separate;\">
            <tr>
              <td bgcolor=\"#4338CA\" style=\"border-radius:6px; mso-padding-alt:0;\">
                <a href=\"{url}\" style=\"display:inline-block; padding:12px 18px; color:#ffffff; text-decoration:none; font-weight:bold; line-height:1;\">비밀번호 재설정하기</a>
              </td>
            </tr>
          </table>
          <div style=\"height:12px; line-height:12px;\">&nbsp;</div>
          <p style=\"margin:0; font-size:12px; color:#6b7280; word-break:break-all; overflow-wrap:anywhere;\">
            또는 링크: <a href=\"{url}\" style=\"color:#4338CA; text-decoration:underline;\">{url}</a>
          </p>
        </td>
      </tr>
    </table>
    """
    text = "비밀번호 재설정 링크: " + url
    return html, text

def build_verification_email(token: str) -> tuple[str, str]:
    verify_url = build_verify_url(token)
    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial, Helvetica, sans-serif; background:#ffffff;">
      <tr>
        <td style="padding:24px; font-size:14px; line-height:1.6; color:#111827;">
          <h3 style="margin:0 0 12px 0; font-size:18px; color:#111827;">이메일 인증</h3>
          <p style="margin:0 0 16px 0;">아래 버튼을 눌러 이메일을 인증하세요.</p>

          <!-- 버튼을 별도 테이블로 감싸서 겹침/깨짐 방지 -->
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 16px 0; border-collapse:separate;">
            <tr>
              <td bgcolor="#4338CA" style="border-radius:6px; mso-padding-alt:0;">
                <a href="{verify_url}"
                   style="display:inline-block; padding:12px 18px; color:#ffffff; text-decoration:none; font-weight:bold; line-height:1;">
                  이메일 인증하기
                </a>
              </td>
            </tr>
          </table>

          <!-- 버튼과 텍스트 링크 사이에 확실한 여백 -->
          <div style="height:12px; line-height:12px;">&nbsp;</div>

          <!-- 긴 URL 줄바꿈 가능하게 처리 -->
          <p style="margin:0; font-size:12px; color:#6b7280; word-break:break-all; overflow-wrap:anywhere;">
            또는 링크: <a href="{verify_url}" style="color:#4338CA; text-decoration:underline;">{verify_url}</a>
          </p>
        </td>
      </tr>
    </table>
    """
    text = "이메일 인증 링크: " + verify_url
    return html, text

def send_email(to: str, subject: str, html: str, text: str | None = None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = to
    if text:
        msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as server:
        server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(msg)
