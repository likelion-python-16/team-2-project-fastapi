# app/main.py
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

# ── 내부 라우터 (각 파일 내 prefix를 신뢰, 여기서 중복 prefix 주지 않음)
from app.routers import health, system, challenges
from app.routers import users as users_router           # users.py 내부 prefix: /api/v1/users
from app.routers import auth as auth_router             # 내부 prefix: /api/v1/auth/*
from app.routers import tags as tags_router             # 내부 prefix: /api/v1/tags/*
from app.routers import users_mypage_chat as my_chat    # 내부 prefix: /api/v1/*
from app.routers import users_mypage_more as my_more    # 내부 prefix: /api/v1/*

from .core.config import settings
from .core.lifespan import lifespan
from .utils.logging import logger


# ── operationId 충돌 방지: 경로+메서드로 고유 ID 생성
def generate_unique_id(route: APIRoute):
    method = sorted(route.methods)[0] if route.methods else "GET"
    return f"{method}_{route.path}".replace("/", "_").replace("{", "").replace("}", "")


app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    generate_unique_id_function=generate_unique_id,
)

# ── CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 정적/템플릿 경로
BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

# ── API 라우터 등록
# ※ 아래 라우터들은 파일 내에 이미 prefix가 정의돼 있으므로 여기서 prefix를 다시 주지 않습니다.

# 비버전(non-versioned) 엔드포인트들 (파일 내 prefix에 따름)
app.include_router(health.router)       # /health/*
app.include_router(system.router)       # /system/*
app.include_router(challenges.router)   # (이 파일이 /challenges 또는 /api/v1/challenges 중 무엇을 쓰는지 확인)

# 버전 프리픽스 포함된 라우터들
app.include_router(auth_router.router)  # /api/v1/auth/*
app.include_router(tags_router.router)  # /api/v1/tags/*
app.include_router(my_chat.router)      # /api/v1/*
app.include_router(my_more.router)      # /api/v1/*
app.include_router(users_router.router) # /api/v1/users/*   ← users.py에 이미 prefix="/api/v1/users"

# ── Pages (HTML 렌더)
@app.get("/", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse, tags=["Pages"])
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})

@app.get("/signin", response_class=HTMLResponse, tags=["Pages"])
async def signin_alias(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/final", response_class=HTMLResponse)
def final_page(request: Request):
    return templates.TemplateResponse("final.html", {"request": request})

@app.get("/full", response_class=HTMLResponse)
def full_page(request: Request):
    return templates.TemplateResponse("full_index.html", {"request": request})

@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request):
    return templates.TemplateResponse("mypage.html", {"request": request})

# ── API info
@app.get("/api", tags=["API Info"])
async def api_info():
    return {
        "message": f"{settings.project_name} API",
        "version": settings.project_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "system_info": "/system/info",
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "users": "/api/v1/users/*",
            "tags": "/api/v1/tags/*",
            # challenges 라우터가 비버전이면 아래 그대로 두고,
            # 버전으로 바꾸면 "/api/v1/challenges/*"로 업데이트하세요.
            "challenges": "/challenges/*",
        },
        "pages": {
            "home": "/",
            "signup": "/signup",
            "login": "/login",
            "signin": "/signin",
            "dashboard": "/dashboard",
            "users": "/users-list",
            "final": "/final",
            "full": "/full",
            "mypage": "/mypage",
        },
        "timestamp": datetime.now().isoformat(),
    }

# ── 개발 실행
if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버 실행…")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
