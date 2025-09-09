# app/main.py
import os
from pathlib import Path
from datetime import datetime
from typing import Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import FormData

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
    users_mypage, users_mypage_chat, users_mypage_more, point_management,
    reviews, reviews_api, notifications, reports
)

# 메트릭 미들웨어
from .core.metrics import MetricsMiddleware, get_metrics
from .routers import auth_social
from .routers import round_pictures, participations, payments, payment_reminders
from app.routers.challengecreating import router as challengecreating_router
from app.routers.challengedetail import router as challengedetail_router
from app.routers.place_picker import router as place_picker_router
from app.routers import chat as chat_router

# Admin routers
from app.routers import admin_auth
from app.routers import admin_pages
from app.routers import admin

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

# 메트릭 미들웨어 추가
app.add_middleware(MetricsMiddleware)

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

# ---------------------------
# HTML Pages
# ---------------------------
@app.get("/home", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page_post(request: Request):
    """HTML 폼으로 /login이 직접 POST될 때를 대비한 폴백 처리.
    정상 플로우는 JS가 /api/v1/auth/login 으로 fetch 하지만,
    JS 바인딩 이전 제출 또는 브라우저 자동 제출 시 여기서 처리합니다.
    """
    try:
        form: FormData = await request.form()
        username = (str(form.get("username") or form.get("login") or "")).strip().lower()
        password = str(form.get("password") or "")
        remember = str(form.get("rememberMe") or "").strip() in ("1","true","on","yes")
        if not username or not password:
            return templates.TemplateResponse(
                "login.html", {"request": request, "error": "아이디/비밀번호를 입력해 주세요."}, status_code=400
            )

        # 동일 로직 사용: API 로그인 함수 호출
        from app.schemas.auth import LoginIn
        from app.routers.auth import login as api_login
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            tokens = api_login(LoginIn(login=username, password=password), db)
        finally:
            db.close()

        # 토큰 저장: JS 기반 흐름과 동일하게 storage에 기록 후 홈으로 이동시키는 미니 페이지 반환
        # remember 체크 시 쿠키도 함께 발급해 서버사이드 렌더링/페이지 전환 호환성 확보
        access_cookie = settings.auth_access_cookie_name or "access_token"
        refresh_cookie = settings.auth_refresh_cookie_name or "refresh_token"
        secure_flag = (settings.auth_cookie_secure if settings.auth_cookie_secure is not None else not settings.debug)
        html = f"""
        <!doctype html><html><head><meta charset=\"utf-8\"><title>Signing in...</title></head>
        <body><script>
        try {{
          var remember = {str(remember).lower()};
          var t = {repr(getattr(tokens,'access_token', ''))};
          var r = {repr(getattr(tokens,'refresh_token', ''))};
          var store = remember ? window.localStorage : window.sessionStorage;
          store.setItem('access_token', t);
          if (r) store.setItem('refresh_token', r);
          if (remember) localStorage.setItem('remember_login','1');
        }} catch(_) {{}}
        window.location.replace('/home');
        </script></body></html>
        """
        resp = HTMLResponse(content=html, status_code=200)
        if remember:
            resp.set_cookie(
                key=access_cookie,
                value=tokens.access_token,
                httponly=settings.auth_cookie_http_only,
                secure=secure_flag,
                samesite=(settings.auth_cookie_samesite or "lax"),
                max_age=settings.jwt_access_token_expire_minutes * 60,
                path=(settings.auth_cookie_path or "/"),
                domain=(settings.auth_cookie_domain or None),
            )
            if getattr(tokens, "refresh_token", None):
                resp.set_cookie(
                    key=refresh_cookie,
                    value=tokens.refresh_token,
                    httponly=settings.auth_cookie_http_only,
                    secure=secure_flag,
                    samesite=(settings.auth_cookie_samesite or "lax"),
                    max_age=settings.jwt_refresh_expire_minutes * 60,
                    path=(settings.auth_cookie_path or "/"),
                    domain=(settings.auth_cookie_domain or None),
                )
        return resp
    except HTTPException as exc:
        msg = exc.detail if isinstance(exc.detail, str) else "로그인에 실패했습니다."
        return templates.TemplateResponse("login.html", {"request": request, "error": msg}, status_code=exc.status_code)
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "로그인 처리 중 오류가 발생했습니다"}, status_code=500)

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

# Support alternate path prefix: /signup/social/* (redirect to /social/*)
@app.get("/signup/social/step1", response_class=HTMLResponse, tags=["Pages"])
async def signup_social_step1_alias():
    return RedirectResponse(url="/social/step1", status_code=307)

@app.get("/signup/social/step2", response_class=HTMLResponse, tags=["Pages"])
async def signup_social_step2_alias():
    return RedirectResponse(url="/social/step2", status_code=307)

@app.get("/signup/social/step3", response_class=HTMLResponse, tags=["Pages"])
async def signup_social_step3_alias():
    return RedirectResponse(url="/social/step3", status_code=307)

# Completion aliases
@app.get("/social/complete", response_class=HTMLResponse, tags=["Pages"])  
async def social_complete_page(request: Request):
    return templates.TemplateResponse("signup_complete_social.html", {"request": request})

@app.get("/signup/social/complete", response_class=HTMLResponse, tags=["Pages"])  
async def signup_social_complete_alias():
    return RedirectResponse(url="/social/complete", status_code=307)

# Social login tokens callback page
@app.get("/auth/callback", response_class=HTMLResponse, tags=["Pages"])
async def auth_callback_page(request: Request):
    return templates.TemplateResponse("auth_callback.html", {"request": request})

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
    """계정 연동 완료 안내 페이지"""
    return templates.TemplateResponse("social_merge_done.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

# Public profile page for a specific user id
@app.get("/users/{user_id}", response_class=HTMLResponse, tags=["Pages"])
async def public_user_profile(request: Request, user_id: int):
    return templates.TemplateResponse("mypage.html", {"request": request, "view_user_id": user_id})

@app.get("/mypage", response_class=HTMLResponse, tags=["Pages"])
async def mypage_page(request: Request):
    return templates.TemplateResponse("mypage.html", {"request": request})

@app.get("/account/edit", response_class=HTMLResponse, tags=["Pages"])
async def account_edit_page(request: Request):
    return templates.TemplateResponse("account_edit.html", {"request": request})

@app.get("/account/email", response_class=HTMLResponse, tags=["Pages"])
async def account_email_page(request: Request):
    return templates.TemplateResponse("account_email.html", {"request": request})

@app.get("/demo", response_class=HTMLResponse, tags=["Pages"])
def get_demo(request: Request):
    return templates.TemplateResponse("demo.html", {"request": request})

# Chat pages
@app.get("/chat", response_class=HTMLResponse, tags=["Pages"])
async def chat_list_page(request: Request):
    return templates.TemplateResponse("chat_list.html", {"request": request})

@app.get("/chat/rooms/{room_id}", response_class=HTMLResponse, tags=["Pages"])
async def chat_room_page(request: Request, room_id: int):
    return templates.TemplateResponse("chat_room.html", {"request": request, "room_id": room_id})

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
def verify_success_page():
    with open("app/templates/verify_success.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/verify/fail", response_class=HTMLResponse, tags=["Email Verification"])
def verify_fail_page():
    with open("app/templates/verify_fail.html", "r", encoding="utf-8") as f:
        content = f.read()  
    return HTMLResponse(content=content)

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

@app.get("/metrics", response_class=PlainTextResponse, tags=["Monitoring"])
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    return get_metrics()

# ---------------------------
# Exception Handlers
# ---------------------------
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    path = request.url.path if request and request.url else ""
    if path.startswith("/admin") and exc.status_code in (401, 403):
        return RedirectResponse(url="/admin/login", status_code=303)
    detail = exc.detail if isinstance(exc.detail, (str, list, dict)) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})

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
app.include_router(payment_reminders.router, prefix="/api/v1")
app.include_router(reviews.router)  # 페이지 라우터 (prefix="/api" 포함)
app.include_router(reviews_api.router, prefix="/api/v1")
app.include_router(notifications.router)  # 이미 prefix가 포함됨
app.include_router(reports.router, prefix="/api/v1")

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
app.include_router(chat_router.router)
app.include_router(users_mypage.router)
app.include_router(users_mypage_chat.router)
app.include_router(users_mypage_more.router)
app.include_router(users_mypage.page_router)

# Admin routes
app.include_router(admin_auth.router)
app.include_router(admin_pages.router)
app.include_router(admin.router, prefix="/api/v1")
app.include_router(point_management.router, prefix="/api/v1")

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
