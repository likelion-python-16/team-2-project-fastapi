# app/routers/payments.py
from __future__ import annotations

import base64
import uuid
import httpx
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.security import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.challenge import Challenge
from app.models.user import User
from app.schemas.payment import (
    PaymentCreateIn, PaymentOut, PaymentUpdateStatusIn,
    RefundCreateIn, RefundOut, TossWebhookIn
)
from app.services.participation_service import get_participation_service
from app.services.payment_service import PaymentService, get_payment_service
from app.schemas.participation import ParticipationCreate
from app.models.payment import PaymentStatus
from app.utils.logging import logger
from datetime import datetime, timezone

router = APIRouter(prefix="/payments", tags=["Payments"])

# 이 라우터 전용 템플릿 엔진
BASE_DIR = Path(__file__).resolve().parents[1]  # app/routers -> app
TEMPLATE_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# ---------------------------
# 내부 유틸
# ---------------------------
def _encode_basic(secret_key: str) -> str:
    """Toss v1 Basic 인증 헤더 생성 ('secretKey:'를 base64)."""
    return "Basic " + base64.b64encode(f"{secret_key}:".encode()).decode()


# ---------------------------
# 결제 CRUD (내부 결제 테이블)
# ---------------------------
@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """결제 레코드 생성 (사전기록용/내부관리용)"""
    challenge = None
    if payload.challenge_id:
        challenge = db.query(Challenge).filter(Challenge.id == payload.challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다")

    payment = service.create_payment(
        user=current_user,
        challenge=challenge,
        amount=payload.amount,
        transaction_type=payload.transaction_type,  # Enum 타입 그대로 전달
        method=payload.method,                      # Enum 타입 그대로 전달
        order_id=payload.order_id,
        order_name=payload.order_name or "",
        payment_key=payload.payment_key,
        metadata_json=payload.metadata_json,
    )
    return payment


@router.post("/{payment_id}/approve", response_model=PaymentOut)
def approve_payment(
    payment_id: int,
    _db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """결제 승인 (내부 상태 갱신)"""
    return service.approve_payment(payment_id)


@router.post("/{payment_id}/fail", response_model=PaymentOut)
def fail_payment(
    payment_id: int,
    body: PaymentUpdateStatusIn,
    _db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """결제 실패 처리 (내부 상태 갱신)"""
    failure_code = (body.failure_code or "UNKNOWN").strip()
    failure_message = (body.failure_message or "결제 실패").strip()
    return service.fail_payment(payment_id, failure_code, failure_message)


@router.post("/{payment_id}/cancel", response_model=PaymentOut)
def cancel_payment(
    payment_id: int,
    body: PaymentUpdateStatusIn,
    _db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """결제 취소 (내부 상태 갱신)"""
    cancel_reason = (body.cancel_reason or "사용자 요청").strip()
    return service.cancel_payment(payment_id, cancel_reason)


@router.post("/{payment_id}/refunds", response_model=RefundOut, status_code=status.HTTP_201_CREATED)
def create_refund(
    payment_id: int,
    body: RefundCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """환불 생성 (내부 기록)"""
    if payment_id != body.payment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payment_id 불일치")
    return service.refund_payment(payment_id, current_user, body.amount, body.reason)


@router.get("/my", response_model=list[PaymentOut])
def get_my_payments(
    challenge_id: Optional[int] = None,
    _db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """내 결제 내역 조회"""
    return service.get_user_payments(current_user.id, challenge_id)


@router.get("/my/refunds", response_model=list[RefundOut])
def get_my_refunds(
    challenge_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내 환불 내역 조회"""
    from app.models.payment import Refund
    
    query = db.query(Refund).filter(Refund.user_id == current_user.id)
    
    if challenge_id:
        query = query.filter(Refund.challenge_id == challenge_id)
    
    refunds = query.order_by(Refund.requested_at.desc()).all()
    return refunds


# ---------------------------
# Toss Webhook
# ---------------------------
@router.post("/webhooks/toss", status_code=status.HTTP_200_OK)
def toss_webhook(
    event: TossWebhookIn,
    db: Session = Depends(get_db),
    service: PaymentService = Depends(get_payment_service),
):
    """
    토스 결제 웹훅
    - 실서비스에선 event 시그니처 검증 필요
    """
    from app.models.payment import Payment

    payment = db.query(Payment).filter(Payment.order_id == event.orderId).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 주문을 찾을 수 없습니다")

    if event.status == "DONE":
        service.approve_payment(payment.id)
    elif event.status in ("CANCELED", "PARTIAL_CANCELED"):
        service.cancel_payment(payment.id, "PG webhook")
    elif event.status == "FAILED":
        service.fail_payment(payment.id, "PG_FAILED", "PG webhook")
    return {"ok": True}


# ---------------------------
# Toss v1 결제 플로우 (단일창)
# ---------------------------
@router.post("/ready")
def payments_ready(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    결제 전 준비 API
    - 프론트가 orderId/amount/orderName/clientKey를 받아 Toss 결제창 호출
    """
    challenge_id = payload.get("challenge_id")
    if not challenge_id:
        raise HTTPException(status_code=400, detail="challenge_id가 필요합니다.")
    
    participation_service = get_participation_service(db)

    # 챌린지 조회
    challenge = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="챌린지를 찾을 수 없습니다.")

    # 실시간 챌린지 상태 확인 (생성자는 draft 상태에서도 결제 가능)
    is_creator = challenge.creator_id == user.id
    if challenge.status not in ["recruiting", "draft"] or (challenge.status == "draft" and not is_creator):
        status_text = {
            'draft': '준비중',
            'active': '진행중', 
            'completed': '완료',
            'cancelled': '취소됨',
            'closed': '정산완료'
        }.get(challenge.status, challenge.status)
        
        if challenge.status == "draft" and not is_creator:
            raise HTTPException(
                status_code=400, 
                detail="이 챌린지는 아직 모집이 시작되지 않았습니다. 생성자가 결제를 완료해주세요."
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"현재 모집중이 아닌 챌린지입니다 (상태: {status_text}). 페이지를 새로고침해주세요."
            )

    # 결제 타입에 따른 금액/상품명
    payment_type = challenge.payment_type.value if getattr(challenge, "payment_type", None) else "free"
    if payment_type == "free":
        raise HTTPException(status_code=400, detail="무료 챌린지입니다. 결제가 필요하지 않습니다.")

    if payment_type == "entry_fee":
        amount = int(challenge.entry_fee or 0)
        order_name = f"[입장비] {challenge.title}"
    elif payment_type == "monthly_fee":
        amount = int(challenge.monthly_fee or 0)
        order_name = f"[월회비] {challenge.title}"
    else:  # both 등
        amount = int(challenge.entry_fee or 0)
        order_name = f"[입장비] {challenge.title}"

    if amount <= 0:
        raise HTTPException(status_code=400, detail="결제 금액이 0보다 커야 합니다.")

    # orderId: 중복 방지
    order_id = f"CH{challenge.id}-U{user.id}-{uuid.uuid4().hex[:12]}"

    # 참여 신청 (생성자는 이미 참여되어 있을 것이므로 확인만)
    try:
        # 생성자가 아닌 경우에만 참여 신청 시도
        if not is_creator:
            participation_service.join_challenge(user, ParticipationCreate(challenge_id=challenge.id))
        else:
            # 생성자인 경우 기존 참여 확인
            participation_service = get_participation_service(db)
            existing_participation = participation_service._get_user_participation(challenge.id, user.id)
            if not existing_participation:
                logger.warning(f"생성자 참여 정보 없음: user_id={user.id}, challenge_id={challenge.id}")
                raise HTTPException(status_code=400, detail="생성자 참여 정보를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"참여 확인 중 오류: {e}")
        raise HTTPException(status_code=400, detail=f"참여 확인 중 오류가 발생했습니다: {str(e)}")

    return {
        "orderId": order_id,
        "amount": amount,
        "orderName": order_name,
        "customerName": user.username or user.name or "고객님",
        "customerEmail": user.email,
        "clientKey": getattr(settings, "toss_client_key", "test_ck_D5GePWvyJnrK0W0k6q8gLzN97Eoq"),
    }


@router.post("/confirm")
def payments_confirm(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    결제 승인 API (success 페이지에서 호출)
    payload: { paymentKey, orderId, amount, challenge_id }
    """
    payment_key = payload.get("paymentKey")
    order_id = payload.get("orderId")
    amount = payload.get("amount")
    challenge_id = payload.get("challenge_id")

    if not payment_key or not order_id or amount is None or challenge_id is None:
        raise HTTPException(status_code=400, detail="paymentKey, orderId, amount, challenge_id가 모두 필요합니다.")

    try:
        amount = int(amount)
        challenge_id = int(challenge_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="amount/challenge_id 형식이 올바르지 않습니다.")

    # 1) Toss 승인
    secret_key = getattr(settings, "toss_secret_key", "test_sk_zXLkKEypNArWmo50nX3lmeaxYG5R")
    auth_header = _encode_basic(secret_key)
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://api.tosspayments.com/v1/payments/confirm",
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
                json={"paymentKey": payment_key, "orderId": order_id, "amount": amount},
            )
        resp.raise_for_status()
        toss_result = resp.json()
    except httpx.HTTPError as e:
        detail = "Toss 승인 실패"
        if getattr(e, "response", None):
            try:
                err_json = e.response.json()
                detail = f"Toss 승인 실패: {err_json.get('message', str(e))}"
            except Exception:
                detail = f"Toss 승인 실패: {e.response.text}"
        raise HTTPException(status_code=400, detail=detail)

    # 2) 참여 처리 먼저, 그 다음 Payment 레코드 생성
    payment_service = get_payment_service(db)
    participation_service = get_participation_service(db)
    
    try:
        # 챌린지 조회
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=404, detail="챌린지를 찾을 수 없습니다")
        
        # 참여 신청 또는 활성화 (FK 제약조건 때문에 먼저 처리)
        existing_participation = participation_service._get_user_participation(challenge_id, user.id)
        
        if not existing_participation:
            # 참여 데이터가 없으면 새로 생성
            from app.schemas.participation import ParticipationCreate
            participation_data = ParticipationCreate(challenge_id=challenge_id)
            participation_service.join_challenge(user, participation_data)
        else:
            # 기존 참여가 있으면 활성화
            participation_service.complete_payment(user_id=user.id, challenge_id=challenge_id)
        
        # Payment 레코드 생성 (참여 레코드가 존재한 후)
        payment = payment_service.create_payment(
            user=user,
            challenge=challenge,
            amount=amount,
            transaction_type="entry_fee",  # PaymentTransactionType enum value
            method="card",  # PaymentMethodType enum value
            order_id=order_id,
            order_name=f"{challenge.title} 참가비",
            payment_key=payment_key
        )
        
        # 결제 승인으로 상태 변경
        payment.status = PaymentStatus.completed
        payment.approved_at = datetime.now(timezone.utc)
        
        # ✅ 생성자가 결제를 완료한 경우 챌린지 상태를 recruiting으로 변경
        if challenge.creator_id == user.id and challenge.status == 'draft':
            from app.models.challenge import ChallengeStatus
            challenge.status = ChallengeStatus.recruiting
            logger.info(f"챌린지 상태 변경: {challenge.id} -> recruiting (생성자 결제 완료)")
        
        db.commit()
        logger.info(f"결제 승인 완료 - Payment ID: {payment.id}, Participation: {user.id}:{challenge_id}")
        
    except Exception as ex:
        db.rollback()
        logger.error(f"결제 승인 후 DB 처리 실패: {ex}")
        raise HTTPException(status_code=500, detail=f"결제는 성공했으나 데이터 처리 중 오류 발생: {str(ex)}")

    return {
        "success": True,
        "message": "결제가 완료되었습니다.",
        "toss_result": toss_result,
        "challenge_id": challenge_id,
    }


# ---------------------------
# 결제 성공/실패 페이지 (템플릿)
# ---------------------------
@router.get("/success", response_class=HTMLResponse)
def payment_success_page(request: Request):
    return templates.TemplateResponse("payments_success.html", {"request": request})


@router.get("/fail", response_class=HTMLResponse)
def payment_fail_page(request: Request):
    return templates.TemplateResponse("payments_fail.html", {"request": request})
