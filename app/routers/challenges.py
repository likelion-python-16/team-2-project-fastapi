from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

# 데이터베이스 관련
from app.core.database import get_db

# 모델들
from app.models.user import User
from app.models.challenge import Challenge
from app.models.participation import Participation  # ✅ 수정됨
from app.models.challenge_round import ChallengeRound

# 스키마들
from app.schemas.challenge import ChallengeCreate, ChallengeResponse, ChallengeUpdate, ChallengeStatus
from app.schemas.challenge_round import ChallengeRoundCreate, ChallengeRoundUpdate, ChallengeRoundResponse

# 라우터 생성
router = APIRouter(
    prefix="/challenges",
    tags=["challenges"]
)

# 챌린지 생성
@router.post("/", response_model=ChallengeResponse)
def create_challenge(
    challenge_data: ChallengeCreate,
    db: Session = Depends(get_db)
):
    """새로운 챌린지 생성"""
    # TODO: 현재 유저 ID 가져오기 (인증 구현 후)
    current_user_id = 1  # 임시값
    
    # 🆕 비즈니스 로직 검증
    # 회비와 참가비 둘 다 설정할 수 없음
    if challenge_data.fee and challenge_data.fee > 0 and challenge_data.participation_fee and challenge_data.participation_fee > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set both fee and participation fee"
        )
    
    # 리워드 사용 시 리워드 내용 필수
    if challenge_data.use_reward and not challenge_data.reward:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reward content is required when use_reward is True"
        )
    
    # 새 챌린지 생성 (모든 필드 포함)
    new_challenge = Challenge(
        title=challenge_data.title,
        description=challenge_data.description,
        start_date=challenge_data.start_date,
        end_date=challenge_data.end_date,
        creator_id=current_user_id,
        # 🆕 새로운 필드들
        fee=challenge_data.fee or 0,
        participation_fee=challenge_data.participation_fee or 0,
        min_participants=challenge_data.min_participants,
        max_participants=challenge_data.max_participants,
        total_rounds=challenge_data.total_rounds,
        min_participation_rate=challenge_data.min_participation_rate or 80,
        use_reward=challenge_data.use_reward or False,
        reward=challenge_data.reward
    )
    
    # DB에 저장
    db.add(new_challenge)
    db.commit()
    db.refresh(new_challenge)
    
    return new_challenge

# 모든 챌린지 조회
@router.get("/", response_model=List[ChallengeResponse])
def get_challenges(db: Session = Depends(get_db)):
    """모든 챌린지 목록 조회"""
    challenges = db.query(Challenge).all()
    return challenges

# ===========================================
# 🆕 회차 관리 API들
# ===========================================

# 특정 챌린지의 회차 목록 조회
@router.get("/{challenge_id}/rounds", response_model=List[ChallengeRoundResponse])
def get_challenge_rounds(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """특정 챌린지의 모든 회차 조회"""
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    rounds = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge_id
    ).order_by(ChallengeRound.round).all()
    
    return rounds

# 회차 생성
@router.post("/{challenge_id}/rounds", response_model=ChallengeRoundResponse)
def create_challenge_round(
    challenge_id: int,
    round_data: ChallengeRoundCreate,
    db: Session = Depends(get_db)
):
    """새 회차 생성"""
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # 같은 회차 번호 중복 확인
    existing_round = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge_id,
        ChallengeRound.round == round_data.round
    ).first()
    
    if existing_round:
        raise HTTPException(status_code=400, detail="Round number already exists")
    
    # 새 회차 생성
    new_round = ChallengeRound(
        challenge_id=challenge_id,
        mode=round_data.mode,
        round=round_data.round,
        processing_at=round_data.processing_at,
        start_time=round_data.start_time,
        finish_time=round_data.finish_time,
        description=round_data.description,
        url=round_data.url,
        lat=round_data.lat,
        lon=round_data.lon,
        geofence_radius_m=round_data.geofence_radius_m,
        zoom_meeting_id=round_data.zoom_meeting_id
    )
    
    db.add(new_round)
    db.commit()
    db.refresh(new_round)
    
    return new_round

# 특정 회차 조회
@router.get("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def get_challenge_round(
    challenge_id: int,
    round_id: int,
    db: Session = Depends(get_db)
):
    """특정 회차 상세 조회"""
    round_obj = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge_id,
        ChallengeRound.id == round_id
    ).first()
    
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    return round_obj

# 회차 수정
@router.put("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def update_challenge_round(
    challenge_id: int,
    round_id: int,
    round_update: ChallengeRoundUpdate,
    db: Session = Depends(get_db)
):
    """회차 정보 수정"""
    round_obj = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge_id,
        ChallengeRound.id == round_id
    ).first()
    
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    # 수정할 필드만 업데이트
    update_data = round_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(round_obj, field, value)
    
    db.commit()
    db.refresh(round_obj)
    
    return round_obj

# 회차 삭제
@router.delete("/{challenge_id}/rounds/{round_id}")
def delete_challenge_round(
    challenge_id: int,
    round_id: int,
    db: Session = Depends(get_db)
):
    """회차 삭제"""
    round_obj = db.query(ChallengeRound).filter(
        ChallengeRound.challenge_id == challenge_id,
        ChallengeRound.id == round_id
    ).first()
    
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    db.delete(round_obj)
    db.commit()
    
    return {"message": "Round deleted successfully"}

# 진행 중인 챌린지만 조회 (경로 충돌 방지를 위해 위로 이동)
@router.get("/active", response_model=List[ChallengeResponse])
def get_active_challenges(db: Session = Depends(get_db)):
    """진행 중인 챌린지만 조회"""
    challenges = db.query(Challenge).filter(Challenge.status == "active").all()
    return challenges

# 챌린지 검색 (제목으로) - /{challenge_id}보다 위로 이동
@router.get("/search", response_model=List[ChallengeResponse])
def search_challenges(
    q: str = Query(..., description="검색어"),
    db: Session = Depends(get_db)
):
    """제목으로 챌린지 검색"""
    challenges = db.query(Challenge).filter(
        Challenge.title.contains(q)
    ).all()
    return challenges

# 챌린지 필터링 - /{challenge_id}보다 위로 이동
@router.get("/filter", response_model=List[ChallengeResponse])
def filter_challenges(
    status: Optional[str] = Query(None, description="상태 필터"),
    creator_id: Optional[int] = Query(None, description="생성자 ID"),
    start_date_from: Optional[date] = Query(None, description="시작일 시작 범위"),
    start_date_to: Optional[date] = Query(None, description="시작일 종료 범위"),
    db: Session = Depends(get_db)
):
    """다양한 조건으로 챌린지 필터링"""
    query = db.query(Challenge)
    
    if status:
        query = query.filter(Challenge.status == status)
    if creator_id:
        query = query.filter(Challenge.creator_id == creator_id)
    if start_date_from:
        query = query.filter(Challenge.start_date >= start_date_from)
    if start_date_to:
        query = query.filter(Challenge.start_date <= start_date_to)
    
    challenges = query.all()
    return challenges

# 상태별 챌린지 조회
@router.get("/status/{status}", response_model=List[ChallengeResponse])
def get_challenges_by_status(
    status: ChallengeStatus,
    db: Session = Depends(get_db)
):
    """상태별 챌린지 조회"""
    challenges = db.query(Challenge).filter(Challenge.status == status.value).all()
    return challenges

# 특정 챌린지 조회 (맨 아래로 이동 - 가장 일반적인 패턴이므로)
@router.get("/{challenge_id}", response_model=ChallengeResponse)
def get_challenge(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """특정 챌린지 상세 조회"""
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    return challenge

# 챌린지 참가
@router.post("/{challenge_id}/join")
def join_challenge(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """챌린지 참가하기"""
    # TODO: 현재 유저 ID 가져오기 (인증 구현 후)
    current_user_id = 2  # 임시값
    
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # 🆕 삭제된 챌린지 체크
    if challenge.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join a deleted challenge"
        )
    
    # 🆕 모집 중인 챌린지만 참가 가능
    if challenge.status != "recruiting":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only join recruiting challenges"
        )
    
    # ✅ 이미 참가했는지 확인 - Participation 사용
    existing_participant = db.query(Participation).filter(
        Participation.challenge_id == challenge_id,
        Participation.user_id == current_user_id,
        Participation.is_active == True
    ).first()
    
    if existing_participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already joined this challenge"
        )
    
    # ✅ 최대 참가자 수 체크 - Participation 사용
    if challenge.max_participants:
        current_participants = db.query(Participation).filter(
            Participation.challenge_id == challenge_id,
            Participation.is_active == True
        ).count()
        
        if current_participants >= challenge.max_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Challenge is full"
            )
    
    # ✅ 참가자 추가 - Participation 사용
    new_participant = Participation(
        challenge_id=challenge_id,
        user_id=current_user_id
    )
    
    db.add(new_participant)
    db.commit()
    
    return {"message": "Successfully joined the challenge"}

# 챌린지 참가자 목록 조회
@router.get("/{challenge_id}/participants")
def get_challenge_participants(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """챌린지 참가자 목록 조회"""
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # ✅ Participation 사용
    participants = db.query(Participation).filter(
        Participation.challenge_id == challenge_id
    ).all()
    
    # 참가자 정보와 함께 반환
    result = []
    for participant in participants:
        user = db.query(User).filter(User.id == participant.user_id).first()  # ✅ user_id → id
        result.append({
            "user_id": participant.user_id,
            "username": user.username if user else "Unknown",
            "joined_at": participant.joined_at,
            "status": participant.status
        })
    
    return result

# 챌린지 참가 취소 (나가기)
@router.delete("/{challenge_id}/leave")
def leave_challenge(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """챌린지 나가기"""
    # TODO: 현재 유저 ID 가져오기 (인증 구현 후)
    current_user_id = 2  # 임시값
    
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # ✅ 참가 여부 확인 - Participation 사용
    participant = db.query(Participation).filter(
        Participation.challenge_id == challenge_id,
        Participation.user_id == current_user_id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a participant of this challenge"
        )
    
    # 챌린지 상태 확인 (진행 중인 챌린지는 나가기 제한할 수도 있음)
    if challenge.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot leave a completed challenge"
        )
    
    # 생성자는 나가기 불가 (챌린지 삭제만 가능)
    if challenge.creator_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creator cannot leave their own challenge. Delete the challenge instead."
        )
    
    # 참가자 삭제
    db.delete(participant)
    db.commit()
    
    return {"message": "Successfully left the challenge"}

# 내가 참가한 챌린지 목록
@router.get("/my-participations", response_model=List[ChallengeResponse])
def get_my_participations(db: Session = Depends(get_db)):
    """내가 참가한 챌린지 목록"""
    # TODO: 현재 유저 ID 가져오기 (인증 구현 후)
    current_user_id = 2  # 임시값
    
    # ✅ 내가 참가한 챌린지들의 ID 조회 - Participation 사용
    participant_challenge_ids = db.query(Participation.challenge_id).filter(
        Participation.user_id == current_user_id
    ).subquery()
    
    # 해당 챌린지들 조회
    challenges = db.query(Challenge).filter(
        Challenge.id.in_(participant_challenge_ids)
    ).all()
    
    return challenges

# 내가 생성한 챌린지 목록
@router.get("/my-challenges", response_model=List[ChallengeResponse])
def get_my_challenges(db: Session = Depends(get_db)):
    """내가 생성한 챌린지 목록"""
    # TODO: 현재 유저 ID 가져오기 (인증 구현 후)
    current_user_id = 1  # 임시값
    
    challenges = db.query(Challenge).filter(
        Challenge.creator_id == current_user_id
    ).all()
    
    return challenges

# 챌린지 수정
@router.put("/{challenge_id}", response_model=ChallengeResponse)
def update_challenge(
    challenge_id: int,
    challenge_update: ChallengeUpdate,
    db: Session = Depends(get_db)
):
    """챌린지 정보 수정"""
    # TODO: 현재 유저가 생성자인지 확인 (인증 구현 후)
    current_user_id = 1  # 임시값
    
    # 챌린지 조회
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # 생성자만 수정 가능 (나중에 인증 구현 시 활성화)
    # if challenge.creator_id != current_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only the creator can update this challenge"
    #     )
    
    # 수정할 필드만 업데이트
    update_data = challenge_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(challenge, field, value)
    
    db.commit()
    db.refresh(challenge)
    
    return challenge

# 챌린지 삭제
@router.delete("/{challenge_id}")
def delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db)
):
    """챌린지 삭제"""
    # TODO: 현재 유저가 생성자인지 확인 (인증 구현 후)
    current_user_id = 1  # 임시값
    
    # 챌린지 조회
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # 생성자만 삭제 가능 (나중에 인증 구현 시 활성화)
    # if challenge.creator_id != current_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only the creator can delete this challenge"
    #     )
    
    # ✅ 참가자가 있는지 확인 - Participation 사용
    participants = db.query(Participation).filter(
        Participation.challenge_id == challenge_id
    ).count()
    
    if participants > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete challenge with participants"
        )
    
    # 챌린지 삭제
    db.delete(challenge)
    db.commit()
    
    return {"message": "Challenge deleted successfully"}

# 챌린지 상태 변경
@router.patch("/{challenge_id}/status")
def update_challenge_status(
    challenge_id: int,
    new_status: ChallengeStatus,
    db: Session = Depends(get_db)
):
    """챌린지 상태 변경"""
    # TODO: 현재 유저가 생성자인지 확인 (인증 구현 후)
    current_user_id = 1  # 임시값
    
    # 챌린지 조회
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found"
        )
    
    # 생성자만 상태 변경 가능 (나중에 인증 구현 시 활성화)
    # if challenge.creator_id != current_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only the creator can change challenge status"
    #     )
    
    # 상태 변경 규칙 검증
    current_status = challenge.status
    
    # recruiting → active: 시작일이 되었을 때
    # active → completed: 종료일이 되었을 때
    # 언제든 → cancelled: 취소 가능
    
    if current_status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change status of completed challenge"
        )
    
    # 상태 업데이트
    challenge.status = new_status.value
    db.commit()
    db.refresh(challenge)
    
    return {
        "message": f"Challenge status updated to {new_status.value}",
        "challenge": challenge
    }