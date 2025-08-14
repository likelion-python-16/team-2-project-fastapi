from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import datetime

# 설정 및 라이프사이클
from .core.config import settings
from .core.lifespan import lifespan

# 로깅 설정
from .utils.logging import logger

# 라우터들
from .routers import users, health, system, challenges, auth

# FastAPI 앱 생성
app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 템플릿 설정
templates = Jinja2Templates(directory="app/templates")

# 📍 API 라우터 등록
app.include_router(health.router)           # /health/*
app.include_router(system.router)          # /system/*
app.include_router(users.router, prefix="/api/v1")  # /api/v1/users/*
app.include_router(challenges.router)      # /challenges/*
app.include_router(auth.router)            # /auth/*

# 🏠 페이지 라우터들 (HTML 페이지)
@app.get("/", response_class=HTMLResponse, tags=["Pages"])
async def home_page(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse, tags=["Pages"])
async def signup_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("signin.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def dashboard_page(request: Request):
    """대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/users-list", response_class=HTMLResponse, tags=["Pages"])
async def users_list_page(request: Request):
    """사용자 목록 페이지"""
    return templates.TemplateResponse("users.html", {"request": request})
@app.get("/final", response_class=HTMLResponse)
def final_page(request: Request):
    return templates.TemplateResponse("final.html", {"request": request})

@app.get("/full", response_class=HTMLResponse)
def full_page(request: Request):
    return templates.TemplateResponse("full_index.html", {"request": request})
# 🔗 API 정보 엔드포인트 (JSON 응답)
@app.get("/api", tags=["API Info"])
async def api_info():
    """API 정보"""
    return {
        "message": f"{settings.project_name} API",
        "version": settings.project_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "system_info": "/system/info",
        "endpoints": {
            "auth": "/auth/*",
            "users": "/api/v1/users/*", 
            "challenges": "/challenges/*",
            "health": "/health/*",
            "system": "/system/*"
        },
        "pages": {
            "home": "/",
            "signup": "/signup",
            "login": "/login",
            "dashboard": "/dashboard",
            "users": "/users-list"
        },
        "timestamp": datetime.now().isoformat()
    }

# 🚀 서버 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 개발 서버를 직접 실행합니다...")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )