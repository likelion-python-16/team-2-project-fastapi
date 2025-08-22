import os
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/files", tags=["Files"])

# /static/pictures 경로
STATIC_DIR = Path("app") / "static"
BASE_DIR = STATIC_DIR / "pictures"
LEGACY_DIR = STATIC_DIR / "_pictures_legacy"

# 1) pictures가 '파일'이면 안전하게 보관 폴더로 이동
if BASE_DIR.exists() and BASE_DIR.is_file():
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    # 원래 파일명을 살리고, 충돌 시 uuid 덧붙임
    src = BASE_DIR
    dst = LEGACY_DIR / src.name
    if dst.exists():
        dst = LEGACY_DIR / f"{src.stem}_{uuid.uuid4().hex}{src.suffix}"
    shutil.move(str(src), str(dst))

# 2) 이제 pictures를 폴더로 보장
BASE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

@router.post("/profile-image")
async def upload_profile_image(file: UploadFile = File(...)):
    name = (file.filename or "").strip()
    ext = Path(name).suffix.lower()

    if ext not in ALLOWED:
        raise HTTPException(400, "허용되지 않는 이미지 형식입니다 (jpg, jpeg, png, gif, webp)")

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = BASE_DIR / safe_name

    try:
        content = await file.read()
        dest_path.write_bytes(content)
    except Exception:
        raise HTTPException(500, "이미지 저장에 실패했습니다")

    # 프론트에서 바로 쓰는 URL (StaticFiles가 /static 으로 마운트되어 있어야 함)
    url = f"/static/pictures/{safe_name}"
    return JSONResponse({"url": url})