import uuid
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/files", tags=["Files"])

# ===== Paths =====
STATIC_DIR = Path("app") / "static"
PICTURES_DIR = STATIC_DIR / "pictures"
LEGACY_DIR = STATIC_DIR / "_pictures_legacy"

UPLOADS_DIR = STATIC_DIR / "uploads"
COVERS_DIR = UPLOADS_DIR / "challenges" / "covers"

def round_dir(challenge_id: int | str, round_id: int | str) -> Path:
    return UPLOADS_DIR / "challenges" / str(challenge_id) / "rounds" / str(round_id)

# 1) pictures가 '파일'이면 안전 보관
if PICTURES_DIR.exists() and PICTURES_DIR.is_file():
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    dst = LEGACY_DIR / PICTURES_DIR.name
    if dst.exists():
        dst = LEGACY_DIR / f"{PICTURES_DIR.stem}_{uuid.uuid4().hex}{PICTURES_DIR.suffix}"
    shutil.move(str(PICTURES_DIR), str(dst))

# 2) 필수 폴더 보장
PICTURES_DIR.mkdir(parents=True, exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

def _ext_or_400(filename: str) -> str:
    ext = Path((filename or "").strip()).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "허용되지 않는 이미지 형식입니다 (jpg, jpeg, png, gif, webp)")
    return ext

def _save_upload_into(dirpath: Path, file: UploadFile) -> str:
    dirpath.mkdir(parents=True, exist_ok=True)
    ext = _ext_or_400(file.filename or "")
    safe = f"{uuid.uuid4().hex}{ext}"
    dest = dirpath / safe
    try:
        content = file.file.read()
        dest.write_bytes(content)
    except Exception:
        raise HTTPException(500, "이미지 저장에 실패했습니다")
    # StaticFiles가 /static 으로 마운트되어 있다고 가정
    rel = dest.relative_to(STATIC_DIR)
    return f"/static/{rel.as_posix()}"

def _list_images(dirpath: Path) -> List[str]:
    if not dirpath.exists():
        return []
    out = []
    for p in sorted(dirpath.iterdir()):
        if p.is_file() and p.suffix.lower() in ALLOWED:
            rel = p.relative_to(STATIC_DIR)
            out.append(f"/static/{rel.as_posix()}")
    return out

# ========= 기존 유지 엔드포인트 =========
@router.post("/profile-image")
async def upload_profile_image(file: UploadFile = File(...)):
    url = _save_upload_into(PICTURES_DIR, file)
    return JSONResponse({"url": url})

@router.post("/challenge-cover")
async def upload_challenge_cover(file: UploadFile = File(...)):
    url = _save_upload_into(COVERS_DIR, file)
    return {"url": url}

# ========= 새로 추가: 회차별 업로드/목록 =========
@router.post("/challenges/{challenge_id}/rounds/{round_id}/pictures")
async def upload_round_pictures(
    challenge_id: int,
    round_id: int,
    files: List[UploadFile] = File(..., description="한 번에 여러 장 업로드 가능"),
):
    if not files:
        raise HTTPException(400, "업로드할 파일이 없습니다.")
    saved = []
    target = round_dir(challenge_id, round_id)
    for f in files:
        saved.append(_save_upload_into(target, f))
    return {"count": len(saved), "urls": saved}

@router.get("/challenges/{challenge_id}/rounds/{round_id}/pictures")
async def list_round_pictures(challenge_id: int, round_id: int):
    target = round_dir(challenge_id, round_id)
    return {"urls": _list_images(target)}

@router.get("/challenges/{challenge_id}/pictures")
async def list_challenge_pictures(challenge_id: int):
    """챌린지의 모든 회차 폴더를 훑어서 URL 목록을 반환"""
    base = UPLOADS_DIR / "challenges" / str(challenge_id) / "rounds"
    urls: List[str] = []
    if base.exists():
        for rd in sorted(base.iterdir()):
            if rd.is_dir():
                urls.extend(_list_images(rd))
    return {"urls": urls}
