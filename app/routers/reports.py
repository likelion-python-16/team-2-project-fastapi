from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.models.report import Report, ReportStatus, ReportAutoEval, AutoDecision
from app.schemas.reports import ReportCreate, ReportOut, ReportAutoEvalOut
from app.services.moderation import run_auto_eval, mask_pii, comment_fingerprint

router = APIRouter(tags=["Reports"])  # /api/v1 붙임은 main.py 에서


def _to_out(report: Report, ae: ReportAutoEval) -> ReportOut:
    return ReportOut(
        id=report.id,
        reporter_id=report.reporter_id,
        reported_id=report.reported_id,
        challenge_id=report.challenge_id,
        reason=report.reason,
        details=report.details,
        created_at=report.created_at,
        auto_eval=ReportAutoEvalOut(
            auto_decision=ae.auto_decision.value if hasattr(ae.auto_decision, "value") else str(ae.auto_decision),
            auto_confidence=int(ae.auto_confidence or 0),
            toxic_score=int(ae.toxic_score or 0),
            rule_flag=bool(ae.rule_flag),
            reporter_trust=int(ae.reporter_trust or 0),
            multi_report_count=int(ae.multi_report_count or 0),
        ),
    )


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1) Report 본체 저장
    report = Report(
        reporter_id=current_user.id,
        reported_id=payload.reported_id,
        challenge_id=payload.challenge_id,
        reason=payload.reason or "text_abuse",
        details=payload.details or mask_pii(payload.comment_text),
        status=ReportStatus.pending,
    )
    db.add(report)
    db.flush()  # id 확보

    # 2) reporter_trust 계산: 과거 정당 신고 비율(간단)
    total = (
        db.query(func.count())
        .select_from(Report)
        .filter(Report.reporter_id == current_user.id)
        .scalar()
        or 0
    )
    true_cnt = (
        db.query(func.count())
        .select_from(Report)
        .filter(Report.reporter_id == current_user.id, Report.is_false_report == False)  # noqa: E712
        .scalar()
        or 0
    )
    if total == 0:
        reporter_trust = 0.5
    else:
        # 지수평활 대신 간단 스무딩(라플라스)
        reporter_trust = (true_cnt + 1) / (total + 2)

    # 3) 같은 텍스트/대상 중복 신고 수 집계(최근 48시간)
    masked = mask_pii(payload.comment_text)
    fp = comment_fingerprint(masked)
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    multi = (
        db.query(func.count())
        .select_from(ReportAutoEval)
        .filter(ReportAutoEval.comment_hash == fp, ReportAutoEval.decided_at >= since)
        .scalar()
        or 0
    )

    # 4) 자동판정 실행
    ae = run_auto_eval(masked, reporter_trust=reporter_trust, multi_report_norm=min(1.0, multi / 5.0))

    # 5) 로그 저장 (정수 스케일 0~100)
    ae_row = ReportAutoEval(
        report_id=report.id,
        comment_text=masked,
        comment_hash=fp,
        toxic_score=int(round(ae.toxic_score * 100)),
        rule_flag=ae.rule_flag,
        reporter_trust=int(round(ae.reporter_trust * 100)),
        multi_report_count=int(multi + 1),
        auto_decision=AutoDecision(ae.auto_decision),
        auto_confidence=int(round(ae.final_score * 100)),
    )
    db.add(ae_row)
    db.commit()
    db.refresh(report)
    db.refresh(ae_row)
    return _to_out(report, ae_row)

