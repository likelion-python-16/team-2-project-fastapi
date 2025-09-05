# app/routers/round_pictures.py
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.challenge_round import ChallengeRound

# RoundPicture 모델이 있는 경우에만 DB 기록 (없어도 업로드는 동작)
try:
    from app.models.round_picture import RoundPicture  # 필드 이름은 url/path 등 환경에 맞게 조정
except Exception:
    RoundPicture = None  # type: ignore

router = APIRouter()

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

@router.post("/challenges/{challenge_id}/rounds/{round_id}/pictures")
async def upload_round_pictures(
    challenge_id: int,
    round_id: int,
    file: Optional[UploadFile] = File(None),              # ✅ 단일 파일 호환
    files: Optional[List[UploadFile]] = File(None),       # ✅ 다중 파일 호환
    db: Session = Depends(get_db),
):
    r = db.query(ChallengeRound).filter(
        ChallengeRound.id == round_id,
        ChallengeRound.challenge_id == challenge_id
    ).first()
    if not r:
        raise HTTPException(404, "Round not found")

    to_save: List[UploadFile] = []
    if files:
        to_save.extend([f for f in files if f is not None])
    if file:
        to_save.append(file)
    if not to_save:
        raise HTTPException(422, "No file(s) provided. Use 'file' or 'files'.")

    base = Path("app/static/uploads/challenges") / str(challenge_id) / "rounds" / str(round_id)
    _ensure_dir(base)

    saved_urls: List[str] = []
    for uf in to_save:
        safe_name = uf.filename or "upload.bin"
        safe_name = safe_name.replace("/", "_").replace("\\", "_")
        dst = base / safe_name
        content = await uf.read()
        dst.write_bytes(content)

        public_url = f"/static/uploads/challenges/{challenge_id}/rounds/{round_id}/{safe_name}"
        saved_urls.append(public_url)

        # 선택: DB 기록 (RoundPicture 모델 필드명에 맞추어 저장)
        if RoundPicture:
            try:
                # url 또는 path 중 환경에 맞게 한쪽만 사용하세요.
                pic = RoundPicture(round_id=round_id, url=public_url)  # 필요시 file_path 등으로 변경
                db.add(pic)
            except Exception:
                pass

    db.commit()
    return {"uploaded": saved_urls}