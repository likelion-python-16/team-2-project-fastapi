from pydantic import BaseModel, ConfigDict

class UserTagsOut(BaseModel):
    user_id: int
    tag_ids: list[int]   # ✅ v2 스타일

class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
