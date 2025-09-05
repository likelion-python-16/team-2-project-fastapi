# app/main.py
import os
from pathlib import Path
from datetime import datetime
from typing import Any
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

# Moved to lifespan.py:
# from app.core.database import SessionLocal
# from app.models import Tag
# from app.services.store import store

# 설정 및 라이프사이클
from .core.config import settings
from .core.lifespan import lifespan

# 로깅 설정
from .utils.logging import logger

# 라우터들
from .routers import (
    users, health, system, challenges, auth, homepage, follow,
    naver_maps, map, files, tags_categories, places, naver_local, pages, tags,
    users_mypage, users_mypage_chat, users_mypage_more
)
from .routers import auth_social
from .routers import round_pictures, participations, payments
from app.routers.challengecreating import router as challengecreating_router
from app.routers.challengedetail import router as challengedetail_router
from app.routers.place_picker import router as place_picker_router

# Admin routers
from app.routers import admin_auth
from app.routers import admin_pages

# FastAPI 앱 생성
app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 세션 미들웨어 (소셜 로그인용)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (한 번만)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Admin HTML UX: redirect unauthenticated/forbidden admin HTML requests
@app.exception_handler(HTTPException)
async def http_exception_to_redirect(request: Request, exc: HTTPException):
    try:
        path = request.url.path or ''
        accepts_html = 'text/html' in (request.headers.get('accept') or '')
        if path.startswith('/admin') and accepts_html and exc.status_code in (401, 403):
            try:
                u = getattr(request.state, 'user', None)
                if u is not None and getattr(u, 'is_admin', False):
                    return RedirectResponse(url='/admin', status_code=303)
            except Exception:
                pass
            return RedirectResponse(url='/admin/login', status_code=303)
    except Exception:
        pass
    # Ensure detail is JSON serializable (enums, datetimes, jinja Undefined, etc.)
    try:
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder({"detail": exc.detail}))
    except TypeError:
        # Fallback: coerce detail to string when non-serializable (e.g., jinja2.Undefined)
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

# Lightweight middleware to inject current user + admin_mode flag from cookie for templates
@app.middleware("http")
async def inject_current_user_from_cookie(request: Request, call_next):
    try:
        token = request.cookies.get("access_token")
        if token:
            # Lazy imports to avoid circulars
            from app.security import verify_token as _verify_token
            from app.core.database import SessionLocal as _SessionLocal
            payload = _verify_token(token)
            if payload and payload.get("sub"):
                db = _SessionLocal()
                try:
                    from app.models.user import User as _User
                    uid = payload.get("sub")
                    user = None
                    try:
                        user = db.query(_User).filter(_User.id == int(uid)).first()
                    except Exception:
                        pass
                    if not user and uid and hasattr(_User, "username"):
                        user = db.query(_User).filter(_User.username == str(uid)).first()
                    if user:
                        request.state.user = user
                        try:
                            request.state.admin_mode = bool(payload.get("admin_mode"))
                        except Exception:
                            request.state.admin_mode = False
                finally:
                    db.close()
    except Exception:
        pass
    response = await call_next(request)
    return response

# ---------------------------
# HTML Pages
# ---------------------------
@app.get("/home", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse, tags=["Pages"])
async def signup_page():
    """기본 회원가입 페이지 - 1단계로 리다이렉트"""
    return RedirectResponse(url="/signup/step1", status_code=303)

@app.get("/signup-social", response_class=HTMLResponse, tags=["Pages"])
async def signup_social_page():
    with open("app/templates/signup_social.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/social/step1", response_class=HTMLResponse, tags=["Pages"])
async def social_signup_step1(request: Request):
    return templates.TemplateResponse("signup1forsocial.html", {"request": request})

@app.get("/social/step2", response_class=HTMLResponse, tags=["Pages"])
async def social_signup_step2(request: Request):
    return templates.TemplateResponse("signup2forsocial.html", {"request": request})

@app.get("/social/step3", response_class=HTMLResponse, tags=["Pages"])
async def social_signup_step3(request: Request):
    return templates.TemplateResponse("signup3forsocial.html", {"request": request})

# Backward-compatible aliases for old links
@app.get("/signup/social/step2", response_class=HTMLResponse, tags=["Pages"])  
async def signup_social_step2_alias():
    return RedirectResponse(url="/social/step2", status_code=307)

@app.get("/signup/social/step3", response_class=HTMLResponse, tags=["Pages"])  
async def signup_social_step3_alias():
    return RedirectResponse(url="/social/step3", status_code=307)

# Completion aliases
@app.get("/social/complete", response_class=HTMLResponse, tags=["Pages"])  
async def social_complete_page(request: Request):
    # 소셜 가입 완료 화면 렌더링
    return templates.TemplateResponse("signup_complete_social.html", {"request": request})

@app.get("/signup/social/complete", response_class=HTMLResponse, tags=["Pages"])  
async def signup_social_complete_alias():
    return RedirectResponse(url="/social/complete", status_code=307)

@app.get("/social/onboarding", response_class=HTMLResponse, tags=["Pages"])
async def social_onboarding():
    """소셜 로그인 후 신규 사용자 온보딩"""
    return RedirectResponse(url="/social/step1", status_code=303)

@app.get("/social/merge", response_class=HTMLResponse, tags=["Pages"])
async def social_merge_page(request: Request):
    """계정 연동 확인 페이지"""
    return templates.TemplateResponse("social_merge.html", {"request": request})

@app.get("/social/merge-done", response_class=HTMLResponse, tags=["Pages"])
async def social_merge_done_page(request: Request):
    """계정 연동 완료 페이지"""
    return templates.TemplateResponse("social_merge_done.html", {"request": request})

# Social login tokens callback page
@app.get("/auth/callback", response_class=HTMLResponse, tags=["Pages"])
async def auth_callback_page(request: Request):
    """Front callback that stores access/refresh from query params and redirects."""
    return templates.TemplateResponse("auth_callback.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})


@app.get("/account/edit", response_class=HTMLResponse, tags=["Pages"])
async def account_edit_page(request: Request):
    return templates.TemplateResponse("account_edit.html", {"request": request})

@app.get("/account/email", response_class=HTMLResponse, tags=["Pages"])
async def account_email_page(request: Request):
    return templates.TemplateResponse("account_email.html", {"request": request})

@app.get("/demo", response_class=HTMLResponse, tags=["Pages"])
def get_demo(request: Request):
    return templates.TemplateResponse("demo.html", {"request": request})

# 생성/상세 페이지: /pages/* 로 고정, 이름 지정
@app.get("/pages/challenges/new", name="page_challenge_create",
         response_class=HTMLResponse, tags=["Pages"])
def page_challenge_create(request: Request):
    return templates.TemplateResponse("challenge_create.html", {"request": request})

@app.get("/pages/challenges/{challenge_id}", name="page_challenge_detail",
         response_class=HTMLResponse, tags=["Pages"])
def page_challenge_detail(request: Request, challenge_id: int):
    return templates.TemplateResponse("challenge_detail.html", {"request": request, "challenge_id": challenge_id})

# 결제 성공/실패 페이지 (Toss 리다이렉트용)
@app.get("/payments/success", response_class=HTMLResponse, tags=["Payment Pages"])
def payment_success_page(request: Request):
    return templates.TemplateResponse("payments_success.html", {"request": request})

@app.get("/payments/fail", response_class=HTMLResponse, tags=["Payment Pages"])  
def payment_fail_page(request: Request):
    return templates.TemplateResponse("payments_fail.html", {"request": request})

# 이메일 인증 성공/실패 페이지
@app.get("/verify/success", response_class=HTMLResponse, tags=["Email Verification"]) 
def verify_success_page(request: Request):
    return templates.TemplateResponse("verify_success.html", {"request": request})

@app.get("/verify/fail", response_class=HTMLResponse, tags=["Email Verification"]) 
def verify_fail_page(request: Request):
    return templates.TemplateResponse("verify_fail.html", {"request": request})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    def scrub(e: dict[str, Any]) -> dict[str, Any]:
        ctx = e.get("ctx")
        if isinstance(ctx, dict):
            e = {**e, "ctx": {k: (str(v) if isinstance(v, BaseException) else v) for k, v in ctx.items()}}
        return e
    return JSONResponse(
        status_code=422,
        content={"detail": [scrub(e) for e in exc.errors()]}
    )

# 네이버 지도 데모들
@app.get("/maps/dynamic", response_class=HTMLResponse, tags=["Pages"])
async def maps_dynamic(request: Request):
    return templates.TemplateResponse(
        "map_dynamic.html",
        {"request": request, "NCP_KEY_ID": settings.naver_maps_client_id}
    )

@app.get("/maps/geocode", response_class=HTMLResponse, tags=["Pages"])
async def maps_geocode(request: Request):
    return templates.TemplateResponse(
        "map_geocode.html",
        {"request": request, "NCP_KEY_ID": settings.naver_maps_client_id}
    )

@app.get("/maps/static", response_class=HTMLResponse, tags=["Pages"])
async def maps_static(request: Request):
    return templates.TemplateResponse(
        "map_static.html",
        {"request": request, "NCP_KEY_ID": settings.naver_maps_client_id}
    )

@app.get("/map", response_class=HTMLResponse, tags=["Pages"])
async def get_map(request: Request):
    ncp_key_id = os.getenv("NAVER_MAPS_CLIENT_ID", "")  # 또는 settings.naver_maps_client_id
    return templates.TemplateResponse("map_dynamic.html", {"request": request, "ncpKeyId": ncp_key_id})

# 루트 → 홈으로
@app.get("/", response_class=HTMLResponse)
async def read_root(_: Request):
    return RedirectResponse(url="/home", status_code=303)

# ---------------------------
# API Info
# ---------------------------
@app.get("/api", tags=["API Info"])
async def api_info():
    return {
        "message": f"{settings.project_name} API",
        "version": settings.project_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "users": "/api/v1/users/*",
            "challenges": "/api/v1/challenges/*",
            "participations": "/api/v1/participations/*",
            "payments": "/api/v1/payments/*",
            "health": "/health/*",
            "system": "/system/*",
        },
        "pages": {
            "home": "/home",
            "signup": "/signup",
            "login": "/login",
            "dashboard": "/dashboard",
            "users": "/users-list",
            "challenge_create": "/pages/challenges/new",
        },
        "timestamp": datetime.now().isoformat()
    }

# ---------------------------
# Router include (중복 제거, 한 번씩만)
# ---------------------------
app.include_router(health.router)
app.include_router(system.router)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(auth_social.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")
app.include_router(participations.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")

app.include_router(places.router)
app.include_router(round_pictures.router)
app.include_router(naver_local.router)
app.include_router(naver_maps.router)
app.include_router(follow.router)
app.include_router(homepage.router)  # 내부 prefix: /api/v1/home
app.include_router(map.router)
app.include_router(files.router, prefix="/api/v1")
app.include_router(pages.router)
app.include_router(tags_categories.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")  # AI 태그 검색 기능
app.include_router(challengecreating_router)
app.include_router(challengedetail_router)
app.include_router(place_picker_router)
app.include_router(users_mypage.router)
app.include_router(users_mypage_chat.router)
app.include_router(users_mypage_more.router)
app.include_router(users_mypage.page_router)

# Admin routes
app.include_router(admin_auth.router)
app.include_router(admin_pages.router)

# ---------------------------
# Seed default tags moved to lifespan.py
# ---------------------------

# ---------------------------
# Dev server entry (optional)
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버를 직접 실행합니다...")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
