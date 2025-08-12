# app/config.py - 환경별 설정 관리
import os
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    # 기본 설정
    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"
    
    # API 설정
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # 데이터베이스 설정
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_user: str = "team_user"
    mysql_password: str = "team_password_123"
    mysql_database: str = "team_project_db"
    mysql_root_password: str = "root_password_123"
    
    # 🆕 JWT 설정 (환경변수 우선)
    jwt_secret: str = os.getenv("JWT_SECRET", "team-project-secret-key-change-this-in-production")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # 🆕 암호화 설정
    fernet_key: str = os.getenv("FERNET_KEY", "")
    
    # 🆕 AWS 설정
    aws_region: str = os.getenv("AWS_REGION", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    
    # CORS 설정
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://54.180.237.228:3000",
        "http://54.180.237.228:8080",
    ]
    
    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    def validate_required_keys(self):
        """필수 키 검증"""
        missing_keys = []
        
        # 프로덕션에서만 필수인 키들
        if self.is_production:
            if not self.fernet_key:
                missing_keys.append("FERNET_KEY")
            if not self.aws_access_key_id:
                missing_keys.append("AWS_ACCESS_KEY_ID")
        
        if missing_keys:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_keys)}")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 환경별 설정 클래스들 (기존 코드 유지)
class DevelopmentSettings(Settings):
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    mysql_host: str = "mysql"

class ProductionSettings(Settings):
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    jwt_secret: str = os.getenv("JWT_SECRET", "CHANGE-THIS-TO-SUPER-SECURE-KEY-FOR-PRODUCTION")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate_required_keys()  # 프로덕션에서만 검증

class TestingSettings(Settings):
    environment: Environment = Environment.TESTING
    debug: bool = True
    mysql_database: str = "test_team_project_db"

@lru_cache()
def get_settings() -> Settings:
    """환경에 따른 설정 반환"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

# 전역 설정 인스턴스
settings = get_settings()

# 🆕 하위 호환성을 위한 개별 변수들
DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket