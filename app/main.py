# app/main.py
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute

from app.core.database import SessionLocal
from app.models import Tag
from app.services.store import store

from .core.config import settings
from .core.lifespan import lifespan
from .utils.logging import logger

# 라우터들
from .routers import (
    users, health, system, challenges, auth, homepage, follow,
    naver_maps, map, files, tags_categories, places, naver_local, pages,
    tags,  # ✅ 추가: 태그 라우터
)
from .routers import round_pictures
# ⛳️ 중복 방지: 아래 한 줄은 제거합니다 (동일 라우터를 두 번 include 하던 원인)
# from app.routers.tags_categories import router as tags_router
from app.routers.challengecreating import router as challengecreating_router
from app.routers.challengedetail import router as challengedetail_router
from app.routers.place_picker import router as place_picker_router

# ✅ users_mypage (API + Page)
from app.routers.users_mypage import (
    router as users_mypage_api_router,        # /api/v1/users/*
    page_router as users_mypage_page_router,  # /mypage
)

# ── operationId 충돌 방지: 경로+메서드로 고유 ID 생성
def generate_unique_id(route: APIRoute):
    method = sorted(route.methods)[0] if route.methods else "GET"
    return f"{method}_{route.path}".replace("/", "_").replace("{", "").replace("}", "")

# ── 앱 생성
app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    generate_unique_id_function=generate_unique_id,  # ✅ 충돌 방지 적용
)

# ── CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 정적 파일 (존재 확인 후 마운트)
BASE_DIR = Path(__file__).resolve().parent          # /app/app
STATIC_DIR = BASE_DIR / "static"                    # /app/app/static
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    logger.warning("Static dir not found: %s", STATIC_DIR)

# ── 템플릿
TEMPLATE_DIR = BASE_DIR / "templates"               # /app/app/templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ---------------------------
# HTML Pages
# ---------------------------
@app.get("/home", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

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

# 네이버 지도 데모들
@app.get("/maps/dynamic", response_class=HTMLResponse, tags=["Pages"])
async def maps_dynamic(request: Request):
    return templates.TemplateResponse("map_dynamic.html", {"request": request, "NCP_KEY_ID": settings.naver_maps_key_id})

@app.get("/maps/geocode", response_class=HTMLResponse, tags=["Pages"])
async def maps_geocode(request: Request):
    return templates.TemplateResponse("map_geocode.html", {"request": request, "NCP_KEY_ID": settings.naver_maps_key_id})

@app.get("/maps/static", response_class=HTMLResponse, tags=["Pages"])
async def maps_static(request: Request):
    return templates.TemplateResponse("map_static.html", {"request": request, "NCP_KEY_ID": settings.naver_maps_key_id})

@app.get("/map", response_class=HTMLResponse, tags=["Pages"])
async def get_map(request: Request):
    ncp_key_id = os.getenv("NAVER_MAPS_CLIENT_ID", "")
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
            "auth": "/api/v1/auth/*",          # 최종 경로 안내
            "users": "/api/v1/users/*",
            "challenges": "/api/v1/challenges/*",
            "health": "/health/*",
            "system": "/system/*",
        },
        "pages": {
            "home": "/home",
            "signup": "/signup",
            "login": "/login",
            "signin": "/signin",
            "dashboard": "/dashboard",
            "users": "/users-list",
            "challenge_create": "/pages/challenges/new",
        },
        "timestamp": datetime.now().isoformat(),
    }

# ---------------------------
# Router include (중복 제거, 한 번씩만)
# ---------------------------
app.include_router(health.router)
app.include_router(system.router)

# users/challenges는 /api/v1 프리픽스와 잘 결합되게 설계되어 있음
app.include_router(users.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")

# ✅ auth는 내부에 이미 /api/v1/auth 프리픽스가 있는 것으로 확인되어, 외부 prefix 제거
app.include_router(auth.router)

app.include_router(places.router)
app.include_router(round_pictures.router)
app.include_router(naver_local.router)
app.include_router(naver_maps.router)
app.include_router(follow.router)
app.include_router(homepage.router)    # 내부 prefix: /api/v1/home
app.include_router(map.router)
app.include_router(files.router, prefix="/api/v1")
app.include_router(pages.router)

# ✅ tags_categories 한 번만 include (중복 제거)
app.include_router(tags_categories.router, prefix="/api/v1")

# ✅ NEW: 태그 라우터 등록 (/api/v1/tags/*)
app.include_router(tags.router)  # ← tags.py가 prefix="/api/v1/tags" 이므로 추가 prefix 불필요

app.include_router(challengecreating_router)
app.include_router(challengedetail_router)
app.include_router(place_picker_router)

# ✅ users_mypage 라우터들 추가
app.include_router(users_mypage_api_router)      # /api/v1/users/*
app.include_router(users_mypage_page_router)     # /mypage

# ---------------------------
# Startup hooks
# ---------------------------
@app.on_event("startup")
def seed_tags_if_empty():
    db = SessionLocal()
    try:
        for name in store.centroid_labels:
            name = (name or "").strip()
            if not name:
                continue
            exists = db.query(Tag).filter(Tag.tag == name).first()
            if not exists:
                db.add(Tag(tag=name, is_active=True))
        db.commit()
    finally:
        db.close()

@app.on_event("startup")
def _print_routes_on_start():
    """디버그: 등록된 라우트 로그로 출력 + 마이페이지 템플릿 존재 확인"""
    try:
        paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
        logger.info("🔎 Registered routes: %s", ", ".join(paths))
        mp = TEMPLATE_DIR / "mypage" / "index.html"
        logger.info("🧩 TEMPLATE_DIR: %s", TEMPLATE_DIR)
        logger.info("🧩 /mypage/index.html exists: %s", mp.exists())
    except Exception as e:
        logger.error("Route/template check failed: %s", e)

# ---------------------------
# Dev server entry (optional)
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버 실행…")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
