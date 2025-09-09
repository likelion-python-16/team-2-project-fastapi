# app/routers/notifications.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.models.notification import Notification, NotificationEvent

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

@router.get("/my-activities")
def get_my_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = Query(False, description="읽지 않은 알림만 반환")
):
    """내 활동 기록 조회 (알림 형태로)"""
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    notifications = q.order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()
    
    activities = []
    for notification in notifications:
        # 아이콘 결정: 이벤트 타입 우선, 없으면 대상 타입 기반 (예: 채팅)
        icon = get_activity_icon(notification.event_type)
        if not icon and getattr(notification, 'target_type', None) == 'chat_room':
            icon = '💬'
        activities.append({
            "id": notification.id,
            "icon": icon or '📄',
            "title": notification.title,
            "content": notification.content,
            "event_type": notification.event_type,
            "target_type": notification.target_type,
            "target_id": notification.target_id,
            "is_read": notification.is_read,
            "created_at": notification.created_at.strftime("%Y-%m-%d %H:%M")
        })
    
    return {
        "activities": activities,
        "total": len(activities)
    }

def get_activity_icon(event_type: NotificationEvent) -> str:
    """이벤트 타입에 따른 아이콘 반환"""
    icons = {
        NotificationEvent.challenge_created: "🎯",
        NotificationEvent.challenge_joined: "👥", 
        NotificationEvent.review_created: "✍️",
        NotificationEvent.review_received: "⭐",
        NotificationEvent.report_received: "⚠️",
        NotificationEvent.warning_received: "🚨",
        NotificationEvent.point_awarded: "💰",
        NotificationEvent.join_completed: "✅",
        NotificationEvent.challenge_deleted: "🗑️",
        NotificationEvent.creator_delegated: "👑",
        NotificationEvent.review_updated: "📝",
        NotificationEvent.refund_succeeded: "💸",
        NotificationEvent.refund_failed: "❌",
        NotificationEvent.notice_posted: "📢",
    }
    return icons.get(event_type, "📄")

@router.post("/mark-read/{notification_id}")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """알림을 읽음으로 표시"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if notification:
        notification.is_read = True
        db.commit()
        return {"message": "알림을 읽음으로 표시했습니다"}
    
    return {"message": "알림을 찾을 수 없습니다"}

@router.post("/mark-all-read")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """모든 알림을 읽음으로 표시"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    return {"message": "모든 알림을 읽음으로 표시했습니다"}
