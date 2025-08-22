# app/routers/tags_categories.py
import json
import os
from fastapi import APIRouter, HTTPException, Query

# /api/v1 는 main.py에서 붙입니다
router = APIRouter(prefix="/tags", tags=["Tags"])

DATA_PATH = os.path.join("data", "category_keywords.json")

def _load_json():
    if not os.path.exists(DATA_PATH):
        raise HTTPException(404, "category_keywords.json not found")
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(500, f"failed to load: {e}")

@router.get("/categories")
def get_categories():
    data = _load_json()
    return list(data.keys())

@router.get("/by-category")
def get_keywords(name: str = Query(..., description="카테고리명")):
    data = _load_json()
    if name not in data:
        raise HTTPException(404, "category not found")
    return {"category": name, "keywords": data[name]}
