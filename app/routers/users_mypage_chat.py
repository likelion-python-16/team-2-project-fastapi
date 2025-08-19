# app/routers/users_mypage_chat.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc
from typing import Optional

from app.db import get_db
from app.routers.auth import get_current_user
from app.deps.pagination import pagination_params  # {skip, limit} 반환(네가 쓰는 util)
from app.models.user import User
from app.models.chat import ChatParticipant
from app.models.chat import ChatRoom
from app.models.chat import ChatMessage

from app.schemas.mypage_chat import (
    ChatRoomBrief, ChatRoomListOut, MannerScoreOut
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# =========================
# F-1-12 참여한 채팅방 목록
# =========================
@router.get("/me/chatrooms", response_model=ChatRoomListOut)
def my_chatrooms(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),  # {"skip": int, "limit": int}
):
    # 내가 참여한 room_id 리스트
    room_ids_stmt = select(ChatParticipant.room_id).where(ChatParticipant.user_id == me.id)
    room_ids = db.execute(room_ids_stmt).scalars().all()

    if not room_ids:
        return ChatRoomListOut(items=[], total=0, skip=pg["skip"], limit=pg["limit"])

    # 총 개수
    total = len(room_ids)

    # 방별 마지막 메시지 시각 서브쿼리
    last_msg_sq = (
        select(
            ChatMessage.room_id.label("room_id"),
            func.max(ChatMessage.created_at).label("last_message_at"),
        )
        .where(ChatMessage.room_id.in_(room_ids))
        .group_by(ChatMessage.room_id)
        .subquery()
    )

    # 방 목록 + last_message_at 조인
    rows = db.execute(
        select(ChatRoom, last_msg_sq.c.last_message_at)
        .outerjoin(last_msg_sq, last_msg_sq.c.room_id == ChatRoom.id)
        .where(ChatRoom.id.in_(room_ids))
        .order_by(desc(last_msg_sq.c.last_message_at), desc(ChatRoom.id))
        .offset(pg["skip"]).limit(pg["limit"])
    ).all()

    items = []
    for room, last_at in rows:
        item = ChatRoomBrief.model_validate(room, from_attributes=True)
        item.last_message_at = last_at
        items.append(item)

    return ChatRoomListOut(items=items, total=total, skip=pg["skip"], limit=pg["limit"])


# =================
# F-1-13 매너 점수
# =================
@router.get("/me/manner", response_model=MannerScoreOut)
def my_manner_score(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    # 최신값 보장
    db.refresh(me)
    return MannerScoreOut(manner_score=int(me.manner_score or 0))
