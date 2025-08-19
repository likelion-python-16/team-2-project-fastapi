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

# 설정 및 라이프사이클
from .core.config import settings
from .core.lifespan import lifespan

# 로깅 설정
from .utils.logging import logger

# 라우터들
from .routers import users, health, system, challenges, auth, homepage, follow, naver_maps, map, files, tags_categories, places, naver_local, pages
from .routers import round_pictures
from app.routers.tags_categories import router as tags_router
from app.routers.challengecreating import router as challengecreating_router
from app.routers.challengedetail import router as challengedetail_router
from app.routers.place_picker import router as place_picker_router

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

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
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

# @app.get("/pages/place-picker", response_class=HTMLResponse, tags=["Pages"])
# def page_place_picker(request: Request, scope: str = "row", rid: int | None = None):
#     """
#     scope=row  : challenge_detail에서 행별로 호출
#     scope=global: (원하면) 전역 장소 선택용
#     """
#     # 네이버/장소 API prefix가 설치별로 다를 수 있어 fallback 두 개를 템플릿에 내려줌
#     return templates.TemplateResponse(
#         "place_picker.html",
#         {
#             "request": request,
#             "scope": scope,
#             "rid": rid,
#             "NAVER_LOCAL_PATH_1": "/naver/local",
#             "NAVER_LOCAL_PATH_2": "/api/v1/naver/local",
#             "PLACES_GEOCODE_1": "/places/geocode",
#             "PLACES_GEOCODE_2": "/api/v1/places/geocode",
#         }
#     )

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
        },
        "timestamp": datetime.now().isoformat()
    }



# ---------------------------
# Router include (중복 제거, 한 번씩만)
# ---------------------------
app.include_router(health.router)
app.include_router(system.router)
app.include_router(users.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")                 # 프론트가 /challenges/* 사용
app.include_router(auth.router, prefix="/api/v1")
app.include_router(places.router)
app.include_router(round_pictures.router)
app.include_router(naver_local.router)
app.include_router(naver_maps.router)
app.include_router(follow.router)
app.include_router(homepage.router)                   # 내부 prefix: /api/v1/home
app.include_router(map.router)
app.include_router(files.router, prefix="/api/v1")
app.include_router(pages.router)
app.include_router(tags_categories.router, prefix="/api/v1")
app.include_router(tags_router, prefix="/api/v1")
app.include_router(challengecreating_router)
app.include_router(challengedetail_router)
app.include_router(place_picker_router) 

# ---------------------------
# Seed default tags on startup
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
