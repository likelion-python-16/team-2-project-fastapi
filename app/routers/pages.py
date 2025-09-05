# app/routers/pages.py
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import json, os
from pathlib import Path

from app.core.database import get_db
from app.core.deps import get_current_user_dual, get_current_user_from_cookie
from app.models.user import User
from app.models.challenge import Challenge, ChallengeStatus
from sqlalchemy.orm import Session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Enhanced data loading with fallbacks
try:
    INTERESTS = json.loads(Path("data/category_keywords.json").read_text(encoding="utf-8"))
except Exception:
    INTERESTS = {
        "취미": ["독서", "영화감상", "음악감상", "게임", "요리", "여행"],
        "운동": ["헬스", "러닝", "수영", "축구", "농구", "테니스", "요가", "필라테스"],
        "학습": ["어학", "프로그래밍", "독서", "자격증", "온라인강의"],
        "라이프스타일": ["다이어트", "금연", "금주", "일찍일어나기", "물마시기"]
    }

# Page metadata for SEO and social sharing
PAGE_METADATA = {
    "signup": {
        "title": "회원가입 - 챌린지 플랫폼",
        "description": "새로운 도전을 시작하세요. 함께하는 챌린지로 목표를 달성하세요.",
        "keywords": "회원가입, 챌린지, 목표달성, 습관형성"
    },
    "login": {
        "title": "로그인 - 챌린지 플랫폼", 
        "description": "계정에 로그인하여 진행 중인 챌린지를 확인하세요.",
        "keywords": "로그인, 계정, 챌린지"
    },
    "home": {
        "title": "챌린지 플랫폼 - 함께 성장하는 도전",
        "description": "다양한 챌린지에 참여하고 목표를 달성하세요. 함께하면 더 쉽게 성공할 수 있습니다.",
        "keywords": "챌린지, 목표달성, 습관형성, 자기계발, 동기부여"
    }
}

# Enhanced signup flow with better UX
@router.get("/signup/step1", response_class=HTMLResponse)
def signup_step1(
    request: Request,
    ref: Optional[str] = Query(None, description="추천인 코드"),
    social: Optional[str] = Query(None, description="소셜 로그인 타입"),
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """회원가입 1단계 - 기본 정보 입력"""
    # Already logged in users redirect to home
    if current_user:
        return RedirectResponse(url="/home", status_code=303)
    
    context = {
        "request": request,
        "page_meta": PAGE_METADATA["signup"],
        "referral_code": ref,
        "social_type": social,
        "step": 1,
        "total_steps": 3
    }
    return templates.TemplateResponse("signup_step1.html", context)

# Legacy endpoint for backward compatibility
@router.get("/signup/step1/legacy", response_class=HTMLResponse)
def signup_step1_legacy(request: Request):
    """회원가입 1단계 (레거시)"""
    return templates.TemplateResponse("signup_step1.html", {"request": request})

@router.get("/signup/step2", response_class=HTMLResponse)
def signup_step2(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """회원가입 2단계 - 추가 정보 입력"""
    # Already logged in users redirect to home
    if current_user:
        return RedirectResponse(url="/home", status_code=303)
    
    context = {
        "request": request,
        "page_meta": PAGE_METADATA["signup"],
        "step": 2,
        "total_steps": 3
    }
    return templates.TemplateResponse("signup_step2.html", context)

# Legacy endpoint
@router.get("/signup/step2/legacy", response_class=HTMLResponse)
def signup_step2_legacy(request: Request):
    return templates.TemplateResponse("signup_step2.html", {"request": request})

@router.get("/signup/step3", response_class=HTMLResponse)
def signup_step3(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """회원가입 3단계 - 관심사 선택 (Enhanced)"""
    # Already logged in users redirect to home
    if current_user:
        return RedirectResponse(url="/home", status_code=303)
    
    # Get popular tags from database for better suggestions
    popular_challenges = []
    try:
        from app.models.tag import Tag, ChallengeTag
        popular_tags = (
            db.query(Tag.tag)
            .join(ChallengeTag, ChallengeTag.tag_id == Tag.id)
            .join(Challenge, Challenge.id == ChallengeTag.challenge_id)
            .filter(
                Challenge.is_deleted == False,
                Challenge.is_public == True
            )
            .group_by(Tag.tag)
            .order_by(db.func.count(ChallengeTag.id).desc())
            .limit(20)
            .all()
        )
        
        # Add popular tags to interests
        if popular_tags:
            INTERESTS["인기 챌린지"] = [tag[0] for tag in popular_tags[:10]]
            
    except Exception:
        pass  # Fallback to default interests if database query fails
    
    context = {
        "request": request,
        "page_meta": PAGE_METADATA["signup"],
        "interests_json": json.dumps(INTERESTS, ensure_ascii=False),
        "step": 3,
        "total_steps": 3
    }
    return templates.TemplateResponse("signup_step3.html", context)

# Legacy endpoint
@router.get("/signup/step3/legacy", response_class=HTMLResponse)
def signup_step3_legacy(request: Request):
    return templates.TemplateResponse(
        "signup_step3.html",
        {"request": request, "interests_json": json.dumps(INTERESTS, ensure_ascii=False)},
    )

@router.get("/signup/complete", response_class=HTMLResponse)
def signup_complete(
    request: Request,
    welcome: bool = Query(False, description="환영 메시지 표시"),
    social: Optional[str] = Query(None, description="소셜 가입 타입")
):
    """회원가입 완료 페이지 (Enhanced)"""
    context = {
        "request": request,
        "page_meta": PAGE_METADATA["signup"],
        "show_welcome": welcome,
        "social_type": social,
        "next_url": "/home"
    }
    return templates.TemplateResponse("signup_complete.html", context)

# Legacy endpoint
@router.get("/signup/complete/legacy", response_class=HTMLResponse)
def signup_complete_legacy(request: Request):
    return templates.TemplateResponse("signup_complete.html", {"request": request})

@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    token: Optional[str] = Query(None, description="비밀번호 재설정 토큰"),
    email: Optional[str] = Query(None, description="이메일 주소")
):
    """비밀번호 재설정 페이지 (Enhanced)"""
    context = {
        "request": request,
        "page_meta": {
            "title": "비밀번호 재설정",
            "description": "비밀번호를 안전하게 재설정하세요."
        },
        "reset_token": token,
        "user_email": email,
        "token_valid": token is not None
    }
    return templates.TemplateResponse("reset_password.html", context)

# Legacy endpoint
@router.get("/reset-password/legacy", response_class=HTMLResponse)
def reset_password_page_legacy(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request})

# New enhanced page endpoints
@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(
    request: Request,
    step: int = Query(1, ge=1, le=3, description="온보딩 단계"),
    current_user: Optional[User] = Depends(get_current_user_from_cookie)
):
    """신규 사용자 온보딩 페이지"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Check if user already completed onboarding
    if hasattr(current_user, 'onboarding_completed') and current_user.onboarding_completed:
        return RedirectResponse(url="/home", status_code=303)
    
    context = {
        "request": request,
        "user": current_user,
        "step": step,
        "total_steps": 3,
        "page_meta": {
            "title": f"시작하기 {step}/3 - 챌린지 플랫폼",
            "description": "챌린지 플랫폼을 시작하기 위한 간단한 설정을 완료하세요."
        },
        "interests_json": json.dumps(INTERESTS, ensure_ascii=False) if step == 2 else None
    }
    
    template_name = f"onboarding_step{step}.html"
    return templates.TemplateResponse(template_name, context)

@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    """소개 페이지"""
    context = {
        "request": request,
        "page_meta": {
            "title": "소개 - 챌린지 플랫폼",
            "description": "챌린지 플랫폼은 함께 목표를 달성하고 성장하는 커뮤니티입니다.",
            "keywords": "소개, 챌린지, 목표달성, 커뮤니티"
        }
    }
    return templates.TemplateResponse("about.html", context)

@router.get("/faq", response_class=HTMLResponse)
def faq_page(request: Request):
    """자주 묻는 질문 페이지"""
    # Common FAQ data
    faqs = [
        {
            "category": "일반",
            "questions": [
                {
                    "question": "챌린지는 어떻게 참여하나요?",
                    "answer": "관심있는 챌린지를 찾아 '참여하기' 버튼을 클릭하시면 됩니다."
                },
                {
                    "question": "참가비는 언제 환불되나요?",
                    "answer": "챌린지 완료 시 성공 조건에 따라 자동으로 환불됩니다."
                }
            ]
        },
        {
            "category": "계정",
            "questions": [
                {
                    "question": "소셜 로그인으로 가입할 수 있나요?",
                    "answer": "네, Google, Naver 소셜 로그인을 지원합니다."
                }
            ]
        }
    ]
    
    context = {
        "request": request,
        "page_meta": {
            "title": "자주 묻는 질문 - 챌린지 플랫폼",
            "description": "챌린지 플랫폼 이용에 대한 자주 묻는 질문과 답변을 확인하세요."
        },
        "faqs": faqs
    }
    return templates.TemplateResponse("faq.html", context)

@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    """개인정보처리방침 페이지"""
    context = {
        "request": request,
        "page_meta": {
            "title": "개인정보처리방침 - 챌린지 플랫폼",
            "description": "개인정보 수집 및 이용에 대한 방침을 확인하세요."
        },
        "last_updated": "2024-01-01"
    }
    return templates.TemplateResponse("privacy.html", context)

@router.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    """이용약관 페이지"""
    context = {
        "request": request,
        "page_meta": {
            "title": "이용약관 - 챌린지 플랫폼",
            "description": "서비스 이용약관을 확인하세요."
        },
        "last_updated": "2024-01-01"
    }
    return templates.TemplateResponse("terms.html", context)

@router.get("/error", response_class=HTMLResponse)
def error_page(
    request: Request,
    code: int = Query(500, description="에러 코드"),
    message: str = Query("알 수 없는 오류가 발생했습니다.", description="에러 메시지")
):
    """에러 페이지"""
    error_messages = {
        400: "잘못된 요청입니다.",
        401: "로그인이 필요합니다.",
        403: "권한이 없습니다.",
        404: "페이지를 찾을 수 없습니다.",
        500: "서버 오류가 발생했습니다."
    }
    
    context = {
        "request": request,
        "error_code": code,
        "error_message": error_messages.get(code, message),
        "page_meta": {
            "title": f"오류 {code} - 챌린지 플랫폼",
            "description": "페이지 로딩 중 오류가 발생했습니다."
        }
    }
    return templates.TemplateResponse("error.html", context)

@router.get("/maintenance", response_class=HTMLResponse)
def maintenance_page(request: Request):
    """점검 페이지"""
    context = {
        "request": request,
        "page_meta": {
            "title": "점검 중 - 챌린지 플랫폼",
            "description": "더 나은 서비스를 위해 점검 중입니다."
        },
        "maintenance_message": "더 나은 서비스를 위해 점검 중입니다. 잠시 후 다시 이용해 주세요.",
        "estimated_time": "30분"
    }
    return templates.TemplateResponse("maintenance.html", context)

@router.get("/sitemap", response_class=HTMLResponse)
def sitemap_page(request: Request):
    """사이트맵 페이지"""
    sitemap_sections = [
        {
            "title": "메인",
            "links": [
                {"name": "홈", "url": "/home"},
                {"name": "대시보드", "url": "/dashboard"},
                {"name": "챌린지 생성", "url": "/pages/challenges/new"}
            ]
        },
        {
            "title": "계정",
            "links": [
                {"name": "로그인", "url": "/login"},
                {"name": "회원가입", "url": "/signup"},
                {"name": "마이페이지", "url": "/mypage"}
            ]
        },
        {
            "title": "정보",
            "links": [
                {"name": "소개", "url": "/about"},
                {"name": "FAQ", "url": "/faq"},
                {"name": "이용약관", "url": "/terms"},
                {"name": "개인정보처리방침", "url": "/privacy"}
            ]
        }
    ]
    
    context = {
        "request": request,
        "page_meta": {
            "title": "사이트맵 - 챌린지 플랫폼",
            "description": "챌린지 플랫폼의 모든 페이지를 한눈에 확인하세요."
        },
        "sitemap_sections": sitemap_sections
    }
    return templates.TemplateResponse("sitemap.html", context)

# API endpoint for page metadata (for dynamic loading)
@router.get("/api/page-meta")
def get_page_metadata(page: str = Query(..., description="페이지 이름")):
    """페이지 메타데이터 API"""
    if page in PAGE_METADATA:
        return {"success": True, "metadata": PAGE_METADATA[page]}
    else:
        return {"success": False, "error": "Page not found"}

# Health check endpoint for pages router
@router.get("/pages-health")
def pages_health():
    """Pages router 상태 확인"""
    return {
        "status": "healthy",
        "service": "pages",
        "templates_loaded": True,
        "interests_count": len(INTERESTS),
        "metadata_pages": len(PAGE_METADATA)
    }
