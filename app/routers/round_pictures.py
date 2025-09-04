# app/routers/round_pictures.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.round_picture import RoundPicture
from app.models.challenge_round import ChallengeRound
from app.models.challenge import Challenge

router = APIRouter(prefix="/challenges/{challenge_id}/rounds/{round_id}/pictures", tags=["round-pictures"])

async def save_to_storage(file: UploadFile) -> str:
    # TODO: 실제 업로드 유틸(S3 등) 연동
    return f"https://cdn.example.com/rounds/{file.filename}"

@router.post("")
async def upload_pictures(
    challenge_id: int,
    round_id: int,
    files: list[UploadFile] = File(..., description="최대 10장"),
    db: Session = Depends(get_db),
):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    rd = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.id == round_id, ChallengeRound.challenge_id == challenge_id)
        .first()
    )
    if not ch or not rd:
        raise HTTPException(404, "Challenge/Round not found")

    count = db.query(RoundPicture).filter(RoundPicture.round_id == round_id).count()
    if count + len(files) > 10:
        raise HTTPException(400, "라운드당 최대 10장까지 업로드 가능합니다.")

    urls = []
    for f in files:
        url = await save_to_storage(f)
        db.add(RoundPicture(round_id=round_id, uploaded_by=None, file_url=url))
        urls.append(url)
    db.commit()
    return {"uploaded": urls}