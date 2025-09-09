from __future__ import annotations
from pydantic import BaseModel
from app.services.predictor import predict_category
from typing import Optional

class TagAIRequest(BaseModel):
    query: str

class TagAIResponse(BaseModel):
    tag: str
    score: float | None = None

class TagCreate(BaseModel):
    tag: str
    icon_url: Optional[str] = None

class TagUpdate(BaseModel):
    tag: Optional[str] = None
    icon_url: Optional[str] = None

class TagResponse(BaseModel):
    id: int
    tag: str
    icon_url: Optional[str] = None

    class Config:
        orm_mode = True