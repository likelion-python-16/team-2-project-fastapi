from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db, init_db

# FastAPI 앱 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    debug=settings.DEBUG
)

# CORS 미들웨어 설정 (개발용 - 프로덕션에서는 제한 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용: 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 앱 시작 시 데이터베이스 초기화
@app.on_event("startup")
def startup_event():
    """앱 시작 시 실행되는 이벤트"""
    print("🚀 FastAPI 서버가 시작됩니다...")
    print(f"📊 데이터베이스: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    init_db()
    print("✅ 데이터베이스 초기화 완료")

# 기본 엔드포인트들
@app.get("/")
def read_root():
    """루트 엔드포인트"""
    return {
        "message": f"환영합니다! {settings.PROJECT_NAME}",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """헬스 체크 엔드포인트"""
    try:
        # 데이터베이스 연결 테스트
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "version": settings.PROJECT_VERSION
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

# TODO: 여기에 팀에서 개발할 라우터들을 추가하세요
# 예시:
# from .routers import users, posts, comments
# app.include_router(users.router, prefix="/api/v1")
# app.include_router(posts.router, prefix="/api/v1")
# app.include_router(comments.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )