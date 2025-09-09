from __future__ import annotations
from typing import Dict, Set, Optional, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from datetime import datetime, timezone

from app.core.database import get_db
from app.security import get_current_user, verify_token
from app.models.user import User
from app.models.chat import ChatRoom, ChatParticipant, ChatMessage
from app.models.notification import Notification
from app.utils.logging import logger

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# ---------------------------
# Helpers
# ---------------------------
def _get_or_create_dm_room(db: Session, user_a: int, user_b: int) -> ChatRoom:
    if user_a == user_b:
        raise HTTPException(400, "자기 자신과의 채팅은 생성할 수 없습니다")

    try:
        # 방 찾기: challenge_id 가 NULL (DM 용) 이고 두 명이 모두 참가자인 방
        sub_a = select(ChatParticipant.room_id).where(ChatParticipant.user_id == user_a)
        sub_b = select(ChatParticipant.room_id).where(ChatParticipant.user_id == user_b)

        room = db.execute(
            select(ChatRoom).where(
                ChatRoom.id.in_(sub_a),
                ChatRoom.id.in_(sub_b),
                ChatRoom.challenge_id.is_(None)  # DM 방 조건 추가
            )
        ).scalars().first()

        if room:
            return room

        # 새 방 생성 (DM): 챌린지 미연동 방
        room = ChatRoom(creator_id=user_a, challenge_id=None)
        db.add(room)
        db.flush()

        for uid in (user_a, user_b):
            db.add(ChatParticipant(room_id=room.id, user_id=uid))
        db.commit()
        db.refresh(room)
        return room
        
    except Exception as e:
        db.rollback()
        logger.error(f"채팅방 생성/조회 오류: {str(e)}")
        raise e


def _ensure_member(db: Session, room_id: int, user_id: int) -> None:
    exists = db.execute(
        select(ChatParticipant.id).where(and_(ChatParticipant.room_id == room_id, ChatParticipant.user_id == user_id))
    ).first()
    if not exists:
        raise HTTPException(403, "채팅방에 참여하지 않았습니다")


# ---------------------------
# REST: Rooms, Messages, Unread
# ---------------------------
@router.post("/rooms/with/{target_user_id}")
async def create_or_get_dm_room(target_user_id: int, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    try:
        if target_user_id == me.id:
            raise HTTPException(400, "자기 자신과의 채팅은 불가합니다")
        
        target = db.get(User, target_user_id)
        if not target:
            raise HTTPException(404, "대상 사용자를 찾을 수 없습니다")
        if not target.is_active:
            raise HTTPException(404, "대상 사용자가 비활성 상태입니다")
        
        room = _get_or_create_dm_room(db, me.id, target_user_id)
        return {"room_id": room.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅방 생성 오류: {str(e)}")
        raise HTTPException(500, f"채팅방 생성 중 오류가 발생했습니다: {str(e)}")


@router.get("/rooms")
async def my_rooms(db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    room_ids = db.execute(
        select(ChatParticipant.room_id).where(ChatParticipant.user_id == me.id)
    ).scalars().all()
    if not room_ids:
        return {"items": []}

    # 마지막 메시지, 미읽음 수
    last_sq = (
        select(ChatMessage.room_id, func.max(ChatMessage.created_at).label("last_at"))
        .where(ChatMessage.room_id.in_(room_ids))
        .group_by(ChatMessage.room_id)
        .subquery()
    )
    unread_sq = (
        select(ChatMessage.room_id, func.count(ChatMessage.id).label("unread"))
        .where(
            and_(
                ChatMessage.room_id.in_(room_ids),
                ChatMessage.sender_id != me.id,
                ChatMessage.is_read == False,
            )
        )
        .group_by(ChatMessage.room_id)
        .subquery()
    )

    rows = db.execute(
        select(ChatRoom, last_sq.c.last_at, func.coalesce(unread_sq.c.unread, 0))
        .outerjoin(last_sq, last_sq.c.room_id == ChatRoom.id)
        .outerjoin(unread_sq, unread_sq.c.room_id == ChatRoom.id)
        .where(ChatRoom.id.in_(room_ids))
        .order_by(func.coalesce(last_sq.c.last_at, ChatRoom.created_at).desc())
    ).all()

    items = []
    for room, last_at, unread in rows:
        items.append({
            "id": room.id,
            "title": None,
            "last_message_at": last_at,
            "unread": int(unread or 0),
        })
    return {"items": items}


@router.get("/rooms/{room_id}/messages")
async def list_messages(
    room_id: int,
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[int] = Query(None, description="해당 ID 미만으로 페이징"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    _ensure_member(db, room_id, me.id)

    q = select(ChatMessage).where(ChatMessage.room_id == room_id)
    if before_id is not None:
        q = q.where(ChatMessage.id < before_id)
    q = q.order_by(ChatMessage.id.desc()).limit(limit)
    rows = list(reversed(db.execute(q).scalars().all()))

    # 읽음 처리: 내가 아닌 발신자의 미읽음 메시지
    db.query(ChatMessage).filter(
        ChatMessage.room_id == room_id,
        ChatMessage.sender_id != me.id,
        ChatMessage.is_read == False,
    ).update({ChatMessage.is_read: True})
    db.commit()

    return {
        "items": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "content": m.content,
                "created_at": (m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at)),
                "is_read": m.is_read,
            } for m in rows
        ]
    }


@router.post("/rooms/{room_id}/read")
async def mark_read(room_id: int, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    _ensure_member(db, room_id, me.id)
    db.query(ChatMessage).filter(
        ChatMessage.room_id == room_id,
        ChatMessage.sender_id != me.id,
        ChatMessage.is_read == False,
    ).update({ChatMessage.is_read: True})
    db.commit()
    return {"ok": True}


@router.get("/unread-count")
async def total_unread(db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    room_ids = select(ChatParticipant.room_id).where(ChatParticipant.user_id == me.id)
    cnt = db.execute(
        select(func.count(ChatMessage.id)).where(
            and_(
                ChatMessage.room_id.in_(room_ids),
                ChatMessage.sender_id != me.id,
                ChatMessage.is_read == False,
            )
        )
    ).scalar() or 0
    return {"unread": int(cnt)}


@router.get("/rooms/{room_id}/meta")
async def room_meta(room_id: int, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    _ensure_member(db, room_id, me.id)
    other = db.execute(
        select(User.id, User.username, User.name)
        .select_from(ChatParticipant)
        .join(User, ChatParticipant.user_id == User.id)
        .where(ChatParticipant.room_id == room_id, ChatParticipant.user_id != me.id)
        .limit(1)
    ).first()
    if not other:
        return {"title": "채팅", "other": None}
    # 항상 username을 타이틀로 사용
    display = other.username
    return {"title": f"{display}님과의 채팅", "other": {"id": other.id, "username": other.username, "name": other.name}}
    room_ids = select(ChatParticipant.room_id).where(ChatParticipant.user_id == me.id)
    cnt = db.execute(
        select(func.count(ChatMessage.id)).where(
            and_(
                ChatMessage.room_id.in_(room_ids),
                ChatMessage.sender_id != me.id,
                ChatMessage.is_read == False,
            )
        )
    ).scalar() or 0
    return {"unread": int(cnt)}


# ---------------------------
# WebSocket manager
# ---------------------------
class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: Dict[int, Set[WebSocket]] = {}
        self.global_connections: Dict[int, WebSocket] = {}  # user_id -> websocket

    async def connect(self, room_id: int, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room_id, set()).add(websocket)

    async def connect_global(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.global_connections[user_id] = websocket

    def disconnect(self, room_id: int, websocket: WebSocket):
        try:
            self.rooms.get(room_id, set()).discard(websocket)
        except Exception:
            pass

    def disconnect_global(self, user_id: int):
        try:
            self.global_connections.pop(user_id, None)
        except Exception:
            pass

    async def broadcast(self, room_id: int, message: dict):
        conns = list(self.rooms.get(room_id, set()))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                # drop dead connections
                self.disconnect(room_id, ws)

    async def send_to_user(self, user_id: int, message: dict):
        ws = self.global_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                # drop dead connections
                self.disconnect_global(user_id)


manager = ConnectionManager()


@router.websocket("/ws/global")
async def global_chat_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    # 글로벌 채팅 알림용 WebSocket
    token = websocket.query_params.get("token")
    logger.info(f"글로벌 WebSocket 연결 시도: token={'있음' if token else '없음'}")
    
    if not token:
        logger.warning("글로벌 WebSocket: 토큰이 없음")
        await websocket.close(code=4401)
        return
        
    data = verify_token(token)
    if not data:
        logger.warning("글로벌 WebSocket: 토큰 검증 실패")
        await websocket.close(code=4401)
        return
        
    user_id = data.get("user_id") or data.get("sub")
    logger.info(f"글로벌 WebSocket: 토큰에서 추출한 user_id={user_id}")
    
    if isinstance(user_id, str):
        u = db.execute(select(User).where(User.username == user_id)).scalars().first()
        user_id = u.id if u else None
        
    if not isinstance(user_id, int):
        logger.warning(f"글로벌 WebSocket: user_id가 정수가 아님: {user_id}")
        await websocket.close(code=4401)
        return

    await manager.connect_global(int(user_id), websocket)
    logger.info(f"글로벌 WebSocket 연결 완료: user_id={user_id}")
    
    try:
        while True:
            # 클라이언트에서 ping을 보내면 pong으로 응답 (연결 유지)
            payload = await websocket.receive_json()
            kind = payload.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        manager.disconnect_global(int(user_id))
        logger.info(f"글로벌 WebSocket 연결 해제: user_id={user_id}")
    except Exception:
        logger.exception("글로벌 WebSocket 오류; 연결 해제")
        manager.disconnect_global(int(user_id))


@router.websocket("/ws/{room_id}")
async def chat_ws(websocket: WebSocket, room_id: int, db: Session = Depends(get_db)):
    # 간단 인증: query param "token"
    token = websocket.query_params.get("token")
    logger.info(f"WebSocket 연결 시도: room_id={room_id}, token={'있음' if token else '없음'}")
    
    if not token:
        logger.warning("WebSocket: 토큰이 없음")
        await websocket.close(code=4401)
        return
        
    data = verify_token(token)
    if not data:
        logger.warning("WebSocket: 토큰 검증 실패")
        await websocket.close(code=4401)
        return
        
    user_id = data.get("user_id") or data.get("sub")
    logger.info(f"WebSocket: 토큰에서 추출한 user_id={user_id}, type={type(user_id)}")
    
    if isinstance(user_id, str):
        # sub 가 username일 수도 있으나, 토큰에 user_id 도 포함해두었으므로 우선 사용
        u = db.execute(select(User).where(User.username == user_id)).scalars().first()
        user_id = u.id if u else None
        logger.info(f"WebSocket: 문자열에서 변환된 user_id={user_id}")
        
    if not isinstance(user_id, int):
        logger.warning(f"WebSocket: user_id가 정수가 아님: {user_id}, type={type(user_id)}")
        await websocket.close(code=4401)
        return

    # 멤버 검증
    try:
        _ensure_member(db, room_id, int(user_id))
        logger.info(f"WebSocket: 멤버 검증 성공 - user_id={user_id}, room_id={room_id}")
    except HTTPException as e:
        logger.warning(f"WebSocket: 멤버 검증 실패 - user_id={user_id}, room_id={room_id}, error={str(e)}")
        await websocket.close(code=4403)
        return

    await manager.connect(room_id, websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            kind = payload.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
                continue
            if kind != "message":
                continue
            content = (payload.get("content") or "").strip()
            client_id = payload.get("client_id")  # 클라이언트가 생성한 임시 ID(중복 방지용)
            if not content:
                continue

            # 저장
            msg = ChatMessage(room_id=room_id, sender_id=int(user_id), content=content)
            db.add(msg)
            try:
                db.commit()
                db.refresh(msg)
                logger.debug(f"Chat saved: room={room_id}, sender={user_id}, id={msg.id}")
            except Exception as e:
                logger.error(f"Chat save failed: room={room_id}, sender={user_id}, error={e}")
                db.rollback()
                await websocket.send_json({"type":"error","message":"메시지 저장 실패"})
                continue

            # Notification for other participants
            try:
                recips = db.execute(
                    select(ChatParticipant.user_id).where(
                        and_(ChatParticipant.room_id == room_id, ChatParticipant.user_id != int(user_id))
                    )
                ).scalars().all()
                for uid in recips:
                    db.add(Notification(
                        user_id=uid,
                        title="새 메시지",
                        content=msg.content[:200],
                        target_type="chat_room",
                        target_id=room_id,
                        is_read=False,
                    ))
                db.commit()
            except Exception:
                db.rollback()

            # 브로드캐스트
            await manager.broadcast(room_id, {
                "type": "message",
                "id": msg.id,
                "room_id": room_id,
                "sender_id": user_id,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "client_id": client_id,
            })
            
            # 글로벌 알림 (채팅방에 있지 않은 참여자들에게)
            try:
                recips = db.execute(
                    select(ChatParticipant.user_id).where(
                        and_(ChatParticipant.room_id == room_id, ChatParticipant.user_id != int(user_id))
                    )
                ).scalars().all()
                
                for uid in recips:
                    # 해당 사용자의 미읽음 메시지 수 계산
                    unread_count = db.execute(
                        select(func.count(ChatMessage.id)).where(
                            and_(
                                ChatMessage.room_id == room_id,
                                ChatMessage.sender_id != uid,
                                ChatMessage.is_read == False
                            )
                        )
                    ).scalar() or 0
                    
                    # 글로벌 WebSocket으로 알림 전송
                    await manager.send_to_user(uid, {
                        "type": "new_message",
                        "room_id": room_id,
                        "unread_count": int(unread_count),
                        "sender_id": user_id,
                        "content": msg.content[:100],
                        "created_at": msg.created_at.isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"글로벌 알림 전송 실패: {e}")
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
    except Exception:
        logger.exception("WebSocket error; disconnecting")
        manager.disconnect(room_id, websocket)
