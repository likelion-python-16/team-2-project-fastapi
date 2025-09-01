# app/main.py

import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import SessionLocal
from app.models import Tag
from app.services.store import store

from .core.config import settings
from .core.lifespan import lifespan
from .utils.logging import logger

# ✅ 필요한 라우터만 가져오기 (중복 제거)
from .routers import (
    users, health, system, challenges, auth, homepage, follow,
    naver_maps,                       # ✔ resolve-place-id 등
    files, tags_categories, places, naver_local
)
from app.routers.place_picker import router as place_picker_router
from app.web.routes_verify import router as verify_pages_router
from app.routers.pages import router as pages_router  # ✅ /signup 등 페이지 라우터
from app.routers import auth_social
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session for OAuth flows (state/nonce)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# Static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------
# Pages (여기서 직접 라우팅)
# ---------------------------
@app.get("/home", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/auth/callback", response_class=HTMLResponse, tags=["Pages"])
async def auth_callback_page(request: Request):
    return templates.TemplateResponse("auth_callback.html", {"request": request})

@app.get("/account/email", response_class=HTMLResponse, tags=["Pages"])
async def account_email_page(request: Request):
    return templates.TemplateResponse("account_email.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/demo", response_class=HTMLResponse, tags=["Pages"])
def get_demo(request: Request):
    return templates.TemplateResponse("demo.html", {"request": request})

@app.get("/pages/challenges/new", name="page_challenge_create",
         response_class=HTMLResponse, tags=["Pages"])
def page_challenge_create(request: Request):
    return templates.TemplateResponse("challenge_create.html", {"request": request})

@app.get("/pages/challenges/{challenge_id}", name="page_challenge_detail",
         response_class=HTMLResponse, tags=["Pages"])
def page_challenge_detail(request: Request, challenge_id: int):
    return templates.TemplateResponse("challenge_detail.html",
                                      {"request": request, "challenge_id": challenge_id})

# ✅ map_dynamic.html 이 기대하는 변수명은 ncpKeyId
@app.get("/maps/dynamic", response_class=HTMLResponse, tags=["Pages"])
async def maps_dynamic(request: Request):
    return templates.TemplateResponse(
        "map_dynamic.html",
        {"request": request, "ncpKeyId": settings.naver_maps_client_id}
    )

@app.get("/maps/geocode", response_class=HTMLResponse, tags=["Pages"])
async def maps_geocode(request: Request):
    return templates.TemplateResponse(
        "map_geocode.html",
        {"request": request, "ncpKeyId": settings.naver_maps_key_id}
    )

@app.get("/maps/static", response_class=HTMLResponse, tags=["Pages"])
async def maps_static(request: Request):
    return templates.TemplateResponse(
        "map_static.html",
        {"request": request, "ncpKeyId": settings.naver_maps_key_id}
    )

# 간편 접근용
@app.get("/map", response_class=HTMLResponse, tags=["Pages"])
async def get_map(request: Request):
    ncp_key_id = os.getenv("NAVER_MAPS_CLIENT_ID", "") or settings.naver_maps_client_id
    return templates.TemplateResponse("map_dynamic.html",
        {"request": request, "ncpKeyId": ncp_key_id})

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
            "challenges": "/challenges/*",
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
            "account_email": "/account/email",
        },
        "timestamp": datetime.now().isoformat()
    }

# ---------------------------
# Routers (중복 없이)
# ---------------------------
app.include_router(health.router)
app.include_router(system.router)
app.include_router(users.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(auth_social.router, prefix="/api/v1")
app.include_router(places.router)                 # /places/*
app.include_router(naver_local.router)            # /naver/local
app.include_router(naver_maps.router)             # /naver/resolve-place-id 등
app.include_router(follow.router)
app.include_router(homepage.router)
app.include_router(files.router, prefix="/api/v1")
app.include_router(tags_categories.router, prefix="/api/v1")  # ✅ 한 번만
app.include_router(place_picker_router)                         # /pages/place-picker
app.include_router(pages_router)                                # ✅ /signup, /signup/step2, ...

# 이메일 인증 성공/실패 페이지
app.include_router(verify_pages_router)

# ---------------------------
# Seed tags
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

if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버를 직접 실행합니다...")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
