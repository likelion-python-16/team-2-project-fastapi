# app/schemas/mypage_chat.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatRoomBrief(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: datetime
    last_message_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2

class ChatRoomListOut(BaseModel):
    items: List[ChatRoomBrief]
    total: int
    skip: int
    limit: int


class MannerScoreOut(BaseModel):
    manner_score: int
